"""Durable pretrade journal and offline execution rehearsal.

Production journals accept previews and read-only observations only. No SDK,
credentials or network code exists here. Simulation databases cannot be opened
as production databases. Submission uncertainty is committed BEFORE dispatch.
"""
import hashlib
import json
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from weex_live_preflight import verify_after_submit


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def timestamp():
    return datetime.now(timezone.utc).isoformat()


class OfflineExchange:
    """Fixed in-memory fixture transport. Deliberately has no SDK/client parameter."""
    def __init__(self, ack=None, fail=False):
        self.ack, self.fail, self.calls = ack, fail, []

    def submit(self, order):
        self.calls.append(json.loads(encoded(order)))
        if self.fail:
            raise TimeoutError('SIMULATED_RESPONSE_LOSS')
        return json.loads(encoded(self.ack))


class Journal:
    def __init__(self, path, *, environment='READ_ONLY'):
        if environment not in ('READ_ONLY', 'SIMULATION'):
            raise ValueError('UNSUPPORTED_ENVIRONMENT')
        self.path, self.environment = Path(path), environment
        with closing(self.connect()) as db, db:
            db.execute('CREATE TABLE IF NOT EXISTS metadata (name TEXT PRIMARY KEY, value TEXT NOT NULL)')
            db.execute("INSERT OR IGNORE INTO metadata VALUES ('environment', ?)", (environment,))
            if db.execute("SELECT value FROM metadata WHERE name='environment'").fetchone()[0] != environment:
                raise PermissionError('JOURNAL_ENVIRONMENT_MISMATCH')
            db.execute('''CREATE TABLE IF NOT EXISTS intents (
                client_id TEXT PRIMARY KEY, signal_id TEXT NOT NULL UNIQUE,
                symbol TEXT NOT NULL, payload TEXT NOT NULL, baseline TEXT NOT NULL,
                blockers TEXT NOT NULL, state TEXT NOT NULL, ack TEXT,
                observation TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)''')
            db.execute('''CREATE TABLE IF NOT EXISTS events (
                seq INTEGER PRIMARY KEY AUTOINCREMENT, client_id TEXT NOT NULL,
                state TEXT NOT NULL, detail TEXT NOT NULL, at TEXT NOT NULL)''')
            db.execute('CREATE TABLE IF NOT EXISTS tp_bindings (client_id TEXT PRIMARY KEY, algo_id TEXT NOT NULL UNIQUE)')

    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA synchronous=FULL')
        return db

    def _event(self, db, client, state, detail):
        db.execute('INSERT INTO events(client_id,state,detail,at) VALUES(?,?,?,?)',
                   (client, state, encoded(detail), timestamp()))

    def prepare(self, signal_id, order, before_positions, blockers):
        if not isinstance(signal_id, str) or not signal_id:
            raise ValueError('MISSING_SIGNAL_ID')
        if not isinstance(order, dict) or not isinstance(before_positions, list) or not isinstance(blockers, list):
            raise ValueError('INVALID_PLAN')
        if not all(isinstance(p, dict) and p.get('symbol') for p in before_positions):
            raise ValueError('INVALID_POSITION_BASELINE')
        side = order.get('positionSide')
        if (not order.get('symbol') or side not in ('LONG', 'SHORT')
                or order.get('side') != ('BUY' if side == 'LONG' else 'SELL')
                or order.get('type') != 'MARKET'):
            raise ValueError('INVALID_ORDER')
        for key in ('quantity', 'tpTriggerPrice'):
            value = Decimal(str(order[key]))
            if not value.is_finite() or value <= 0:
                raise ValueError('INVALID_ORDER_NUMBER')
        if any(p['symbol'] == order['symbol'] for p in before_positions):
            raise ValueError('MANUAL_OR_EXISTING_EXPOSURE')
        prefix = 'wxsim_' if self.environment == 'SIMULATION' else 'wxpreview_'
        client = prefix + hashlib.sha256(signal_id.encode()).hexdigest()[:24]
        payload = encoded({**order, 'newClientOrderId': client})
        baseline = encoded(before_positions)
        reasons = encoded(sorted(set(blockers)))
        with closing(self.connect()) as db:
            db.execute('BEGIN IMMEDIATE')
            old = db.execute('SELECT * FROM intents WHERE signal_id=?', (signal_id,)).fetchone()
            if old:
                db.rollback()
                if old['payload'] != payload or old['baseline'] != baseline or old['blockers'] != reasons:
                    raise ValueError('IMMUTABLE_INTENT_CONFLICT')
                return self.get(client)
            now = timestamp()
            db.execute('INSERT INTO intents VALUES(?,?,?,?,?,?,?,NULL,NULL,?,?)',
                       (client, signal_id, order['symbol'], payload, baseline, reasons, 'PREPARED_BLOCKED', now, now))
            self._event(db, client, 'PREPARED_BLOCKED', {'environment': self.environment})
            db.commit()
        return self.get(client)

    def get(self, client):
        with closing(self.connect()) as db:
            row = db.execute('SELECT * FROM intents WHERE client_id=?', (client,)).fetchone()
        if row is None:
            raise KeyError('UNKNOWN_INTENT')
        data = dict(row)
        for key in ('payload', 'baseline', 'blockers', 'ack', 'observation'):
            data[key] = json.loads(data[key]) if data[key] is not None else None
        data.update(canSubmit=False, canClose=False)
        return data

    def overview(self):
        with closing(self.connect()) as db:
            counts = dict(db.execute('SELECT state,COUNT(*) FROM intents GROUP BY state').fetchall())
        return {'environment': self.environment, 'states': counts, 'total': sum(counts.values()),
                'canSubmit': False, 'canClose': False}

    def clients(self):
        with closing(self.connect()) as db:
            return [r[0] for r in db.execute('SELECT client_id FROM intents ORDER BY created_at')]

    def simulate_submit_once(self, client, transport):
        # Both checks precede any state mutation or transport call. No live path.
        if self.environment != 'SIMULATION' or type(transport) is not OfflineExchange:
            raise PermissionError('REAL_SUBMISSION_DISABLED')
        with closing(self.connect()) as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT * FROM intents WHERE client_id=?', (client,)).fetchone()
            if row is None:
                raise KeyError('UNKNOWN_INTENT')
            if row['state'] != 'PREPARED_BLOCKED':
                db.rollback()
                return self.get(client)  # Never retry a previously claimed intent.
            if json.loads(row['blockers']):
                raise PermissionError('PRETRADE_BLOCKERS')
            db.execute("UPDATE intents SET state='SUBMISSION_UNKNOWN',updated_at=? WHERE client_id=?", (timestamp(), client))
            self._event(db, client, 'SUBMISSION_UNKNOWN', {'reason': 'COMMITTED_BEFORE_DISPATCH'})
            db.commit()
        try:
            ack = transport.submit(json.loads(row['payload']))
        except Exception as exc:
            with closing(self.connect()) as db, db:
                self._event(db, client, 'SUBMISSION_UNKNOWN', {'error': type(exc).__name__})
            return self.get(client)
        state = 'SUBMISSION_UNKNOWN'
        if isinstance(ack, dict) and ack.get('success') is False:
            state = 'ORDER_REJECTED'
        elif (isinstance(ack, dict) and ack.get('success') is True
              and ack.get('clientOrderId') == client and ack.get('orderId')):
            state = 'ACKNOWLEDGED'
        with closing(self.connect()) as db, db:
            db.execute("UPDATE intents SET state=CASE WHEN state='SUBMISSION_UNKNOWN' THEN ? ELSE state END,ack=?,updated_at=? WHERE client_id=?",
                       (state, encoded(ack), timestamp(), client))
            self._event(db, client, state, {'reason': 'SIMULATED_RESPONSE'})
        return self.get(client)

    def bind_simulated_tp(self, client, *, request, ack):
        if self.environment != 'SIMULATION':
            raise PermissionError('LIVE_TP_BINDING_NOT_AVAILABLE')
        item = self.get(client)
        intent = item['payload']
        if (item['state'] != 'TP_NOT_CONFIRMED' or not isinstance(ack, dict)
                or ack.get('success') is not True or not ack.get('algoId')
                or request.get('clientAlgoId') != 'wxtp_' + client[6:]
                or ack.get('clientAlgoId') != request.get('clientAlgoId')
                or request.get('symbol') != intent['symbol']
                or request.get('positionSide') != intent['positionSide']
                or request.get('reduceOnly') is not True
                or request.get('side') != ('SELL' if intent['positionSide'] == 'LONG' else 'BUY')
                or request.get('type') != 'TAKE_PROFIT_MARKET'
                or request.get('quantity') != intent['quantity']
                or request.get('triggerPrice') != intent['tpTriggerPrice']):
            raise ValueError('TP_ACK_NOT_BOUND_TO_INTENT')
        with closing(self.connect()) as db, db:
            db.execute('INSERT INTO tp_bindings VALUES(?,?)', (client, str(ack['algoId'])))
            self._event(db, client, item['state'], {'simulatedTpId': str(ack['algoId'])})

    def observe(self, client, snapshot):
        """Persist fresh exchange evidence, without retry, ownership transfer or writes."""
        with closing(self.connect()) as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT * FROM intents WHERE client_id=?', (client,)).fetchone()
            if row is None:
                raise KeyError('UNKNOWN_INTENT')
            item = dict(row)
            if item['state'] == 'CLOSED_BY_MATCHED_TP':
                db.rollback()
                return json.loads(item['observation'])
            if item['state'] == 'PREPARED_BLOCKED':
                db.rollback()
                return {'state': 'PREPARED_BLOCKED', 'reason': 'NEVER_DISPATCHED', 'canSubmit': False, 'canClose': False}
            ack = json.loads(item['ack']) if item['ack'] else None
            ack = ack if isinstance(ack, dict) else None
            orders = snapshot.get('orders', [])
            if not isinstance(orders, list):
                orders = []
            # A lost acknowledgement may be replaced only by an exact exchange order match.
            matches = [o for o in orders if isinstance(o, dict) and o.get('clientOrderId') == client]
            rejected = ack is not None and ack.get('success') is False
            if (not ack or ack.get('success') is not True) and not rejected:
                if len(matches) == 1 and matches[0].get('orderId'):
                    ack = {'success': True, 'orderId': matches[0]['orderId'], 'clientOrderId': client}
            binding = db.execute('SELECT algo_id FROM tp_bindings WHERE client_id=?', (client,)).fetchone()
            result = verify_after_submit(
                client_order_id=client, ack=ack, orders=orders,
                positions=snapshot.get('positions'), tp_orders=snapshot.get('tp_orders'),
                intent=json.loads(item['payload']), trades=snapshot.get('trades'),
                before_positions=json.loads(item['baseline']), expected_tp_id=binding[0] if binding else None,
                snapshot_complete=snapshot.get('complete') is True,
                snapshot_age_ms=snapshot.get('age_ms'))
            if rejected and matches:
                result = {'state': 'RECONCILIATION_REQUIRED', 'reason': 'REJECTION_CONTRADICTS_ORDER', 'canSubmit': False, 'canClose': False}
            db.execute('UPDATE intents SET state=?,observation=?,updated_at=? WHERE client_id=?',
                       (result['state'], encoded(result), timestamp(), client))
            self._event(db, client, result['state'], result)
            db.commit()
        return result

    def observe_close(self, client, **evidence):
        with closing(self.connect()) as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT payload,observation,state FROM intents WHERE client_id=?', (client,)).fetchone()
            if row is None:
                raise KeyError('UNKNOWN_INTENT')
            if row['state'] == 'CLOSED_BY_MATCHED_TP':
                db.rollback()
                return json.loads(row['observation'])
            result = verify_tp_close(entry=json.loads(row['observation'] or '{}'),
                                     intent=json.loads(row['payload']), **evidence)
            if result['state'] == 'CLOSED_BY_MATCHED_TP':
                db.execute('UPDATE intents SET state=?,observation=?,updated_at=? WHERE client_id=?',
                           (result['state'], encoded(result), timestamp(), client))
            self._event(db, client, result['state'], result)
            db.commit()
        return result


def verify_tp_close(*, entry, intent, algo, exit_order, trades, positions, complete, age_ms):
    """A disappeared position is not proof of TP execution; require the entire chain."""
    blocked = {'state': 'CLOSE_RECONCILIATION_REQUIRED', 'canSubmit': False, 'canClose': False}
    try:
        if (complete is not True or not isinstance(age_ms, (float, int)) or not 0 <= age_ms <= 5000
                or entry.get('state') != 'OPEN_WITH_MATCHED_TP'):
            return blocked
        symbol, side = intent['symbol'], intent['positionSide']
        oid = str(exit_order['orderId'])
        if (str(algo['algoId']) != entry['tpId'] or algo['algoStatus'] != 'FILLED'
                or str(algo['actualOrderId']) != oid or algo['symbol'] != symbol
                or algo['positionSide'] != side or exit_order['symbol'] != symbol
                or algo['side'] != ('SELL' if side == 'LONG' else 'BUY')
                or algo.get('orderType') != 'TAKE_PROFIT_MARKET' or algo.get('reduceOnly') is not True
                or Decimal(str(algo['quantity'])) != Decimal(entry['filledQty'])
                or Decimal(str(algo['triggerPrice'])) != Decimal(intent['tpTriggerPrice'])
                or exit_order['positionSide'] != side
                or exit_order['side'] != ('SELL' if side == 'LONG' else 'BUY')
                or exit_order.get('reduceOnly') is not True or exit_order['status'] != 'FILLED'):
            return blocked
        qty = Decimal(entry['filledQty'])
        if Decimal(str(exit_order['executedQty'])) != qty:
            return blocked
        if not isinstance(positions, list) or any(not isinstance(p, dict) or not p.get('symbol') or p['symbol'] == symbol for p in positions):
            return blocked
        total, ids = Decimal(0), set()
        for trade in trades:
            if (str(trade['orderId']) != oid or trade['symbol'] != symbol
                    or trade['positionSide'] != side or trade['side'] != exit_order['side']):
                return blocked
            identity, amount = str(trade['id']), Decimal(str(trade['qty']))
            if not identity or identity in ids or not amount.is_finite() or amount <= 0:
                return blocked
            ids.add(identity); total += amount
        if not ids or not qty.is_finite() or qty <= 0 or total != qty:
            return blocked
        return {'state': 'CLOSED_BY_MATCHED_TP', 'exitOrderId': oid, 'filledQty': str(qty),
                'canSubmit': False, 'canClose': False}
    except (KeyError, TypeError, ValueError, ArithmeticError):
        return blocked
