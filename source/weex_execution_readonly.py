"""Bounded SDK GET observations for the durable execution journal. No order writes."""
import time


def pages(reader, operation, *, identity, start, max_pages=10, **query):
    result, seen = [], set()
    for page in range(start, start + max_pages):
        batch = reader(operation, page=page, limit=100, **query)
        if not isinstance(batch, list):
            raise ValueError('INVALID_PAGE')
        for row in batch:
            if not isinstance(row, dict) or not row.get(identity) or not row.get('symbol'):
                raise ValueError('INVALID_RECORD')
            ident = str(row[identity])
            if ident in seen:
                raise ValueError('REPEATED_PAGE_OR_ID')
            seen.add(ident); result.append(row)
        if len(batch) < 100:
            return result
    raise ValueError('INCOMPLETE_PAGINATION')


def collect(reader, item, *, now_ms=None):
    """Order ID lookup when known, bounded history otherwise. Absence never permits retry."""
    start = time.monotonic()
    end_ms = int(time.time() * 1000) if now_ms is None else now_ms
    symbol, client = item['symbol'], item['client_id']
    ack = item.get('ack') or {}
    result = {'complete': False, 'orders': [], 'positions': [], 'tp_orders': [], 'trades': [], 'age_ms': 0}
    try:
        opened = pages(reader, 'get_capi_v3_openOrders', identity='orderId', start=0, symbol=symbol)
        if ack.get('success') is True and ack.get('orderId'):
            order = reader('get_capi_v3_order', orderId=ack['orderId'])
            history = [order]
        else:
            history = pages(reader, 'get_capi_v3_order_history', identity='orderId', start=0,
                            symbol=symbol, startTime=end_ms - 24*3600*1000, endTime=end_ms)
        # Same ID can occur in both endpoints. Conflicting observations are not reconciled silently.
        combined = {}
        for row in history + opened:
            if not isinstance(row, dict) or row.get('symbol') != symbol or not row.get('orderId'):
                raise ValueError('INVALID_ORDER_OBSERVATION')
            key = str(row['orderId'])
            if key in combined:
                for field in ('clientOrderId', 'symbol', 'side', 'positionSide', 'status', 'executedQty'):
                    if row.get(field) != combined[key].get(field):
                        raise ValueError('ORDER_CHANGED_DURING_SNAPSHOT')
            combined[key] = row
        matches = [row for row in combined.values() if row.get('clientOrderId') == client]
        # Old unrelated history is not same-cycle activity. Current open orders still veto ambiguity.
        selected = {str(row['orderId']): row for row in matches + opened}
        result['orders'] = list(selected.values())
        if len(matches) != 1:
            raise ValueError('ORDER_NOT_FOUND_OR_AMBIGUOUS_NO_RETRY')
        trades = reader('get_capi_v3_userTrades', symbol=symbol, orderId=matches[0]['orderId'], limit=100)
        if not isinstance(trades, list) or len(trades) >= 100:
            raise ValueError('FILLS_INCOMPLETE')
        result['trades'] = trades
        result['tp_orders'] = pages(reader, 'get_capi_v3_openAlgoOrders', identity='algoId', start=1, symbol=symbol)
        positions = reader('get_capi_v3_account_position_allPosition')
        if not isinstance(positions, list) or any(not isinstance(p, dict) or not p.get('symbol') for p in positions):
            raise ValueError('INVALID_POSITION_SNAPSHOT')
        result['positions'] = positions
        result['complete'] = True
    except Exception as exc:
        # No exception text: SDK exceptions may contain signed request details.
        result['error'] = type(exc).__name__
    result['age_ms'] = (time.monotonic() - start)*1000
    if result['age_ms'] > 5000:
        result['complete'] = False
        result['error'] = 'SNAPSHOT_WINDOW_EXCEEDED'
    result.update(canRetry=False, canSubmit=False, canClose=False)
    return result


def recover(journal, reader, open_orders):
    """Restart recovery observes only; no absence or partial response can permit resubmission."""
    results = []
    for client in journal.clients():
        item = journal.get(client)
        if item['state'] == 'PREPARED_BLOCKED':
            if any(row.get('clientOrderId') == client for row in open_orders):
                results.append({'clientOrderId': client, 'state': 'UNEXPECTED_EXCHANGE_ORDER', 'canRetry': False})
            continue
        if item['state'] in ('ORDER_REJECTED', 'CLOSED_BY_MATCHED_TP'):
            continue
        snapshot = collect(reader, item)
        result = journal.observe(client, snapshot)
        results.append({'clientOrderId': client, **result, 'canRetry': False})
    return {'checkedIntents': len(journal.clients()), 'observations': results,
            'ordersSubmitted': False, 'canRetry': False, 'canClose': False}
