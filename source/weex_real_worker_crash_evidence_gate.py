"""Independent, fail-closed real-WEEX crash evidence checker.

Never submits/cancels/closes orders. Requires an actual production worker
Lifecycle entry journal plus independently verified real exchange order,
fills, protective stop history, reduce-only close, and a flat account.
An offline/demo/read-side process crash cannot satisfy this certificate.
"""
import hashlib,json,sqlite3
from pathlib import Path
from decimal import Decimal as D,InvalidOperation
from datetime import datetime,timezone

ROOT=Path(__file__).resolve().parent
NAME='weex_real_worker_crash_attestation.json'
SCOPE='WEEX_PRODUCTION_WORKER_ENTRY_ACK_CRASH_V1'
HOST='https://api-contract.weex.com'

def money(value):
    try:
        out=D(str(value))
        return out if out.is_finite() and out>0 else None
    except (ValueError,InvalidOperation,TypeError):
        return None

def _one_fill(rows,oid,expected,side):
    return (isinstance(rows,list) and bool(rows) and len(rows)<100 and
        all(str(x.get('orderId'))==str(oid) and x.get('side')==side for x in rows) and
        len({str(x.get('id')) for x in rows})==len(rows) and
        sum((money(x.get('qty')) or D(0) for x in rows),D(0))==expected)

def certify(root=ROOT,reader=None):
    root=Path(root)
    proofpath=root/NAME
    if not proofpath.is_file():return {'certified':False,'reason':'NO_REAL_WORKER_CRASH_EVIDENCE'}
    try:
        evidence=json.loads(proofpath.read_text(encoding='utf-8'))
        if (evidence.get('scope')!=SCOPE or evidence.get('host')!=HOST or
            evidence.get('worker')!='weex_live_worker.py' or
            evidence.get('lifecycle')!='weex_lifecycle.py' or
            evidence.get('childExitCode')!=79 or
            evidence.get('phase')!='ENTRY_ACK_RETURNED_BEFORE_SQLITE_ACK' or
            evidence.get('networkEntryDispatches')!=1 or
            evidence.get('entryRetries')!=0 or
            evidence.get('restartNewProcess') is not True or
            evidence.get('stopActiveBeforeClose') is not True or
            evidence.get('supervisedExit') is not True or
            evidence.get('independentAudit') is not True or
            evidence.get('exchangeWritesDuringAudit')!=0):
            return {'certified':False,'reason':'MISSING_REAL_WORKER_CRASH_PROVENANCE'}
        manifest=json.loads((root/'live_release_manifest.json').read_text(encoding='utf-8'))
        for name,key in (('weex_live_worker.py','workerSha256'),
                         ('weex_lifecycle.py','lifecycleSha256')):
            digest=hashlib.sha256((root/name).read_bytes()).hexdigest()
            if manifest.get('sha256',{}).get(name)!=digest or evidence.get(key)!=digest:
                return {'certified':False,'reason':'UNTRUSTED_WORKER_BUILD'}
        tid=evidence['tradeId'];eid=str(evidence['entryOrderId'])
        cid=evidence['clientOrderId'];closeid=str(evidence['closeOrderId'])
        stopid=str(evidence['stopAlgoId'])
        symbol=evidence['symbol'];qty=money(evidence['quantity'])
        if (not tid.startswith('wxentry_') or tid!=cid or
            not symbol.endswith('USDT') or not eid.isdigit() or
            not closeid.isdigit() or not stopid.isdigit() or qty is None):
            return {'certified':False,'reason':'INVALID_ORDER_IDENTITY'}
        # This MUST be the actual production worker journal, not a standalone
        # pilot's private JSON or a test-only SQLite database.
        db=root/'weex_user_live_lifecycle.sqlite3'
        conn=sqlite3.connect('file:'+db.resolve().as_posix()+'?mode=ro',uri=True)
        try:
            conn.row_factory=sqlite3.Row;conn.execute('PRAGMA query_only=ON')
            trade=conn.execute('SELECT plan FROM trades_v1 WHERE id=?',(tid,)).fetchone()
            entry=conn.execute('SELECT operation,payload,state,response FROM writes_v1 WHERE trade_id=? AND kind=\'ENTRY\'',(tid,)).fetchone()
        finally:conn.close()
        if not trade or not entry or entry['operation']!='post_capi_v3_order' or entry['state']!='UNKNOWN' or entry['response'] is not None:
            return {'certified':False,'reason':'NOT_A_WORKER_PRE_ACK_CRASH'}
        plan=json.loads(trade['plan'])['entry'];payload=json.loads(entry['payload'])
        if payload!=plan or plan.get('newClientOrderId')!=cid or plan.get('symbol')!=symbol or money(plan.get('quantity'))!=qty:
            return {'certified':False,'reason':'DURABLE_INTENT_MISMATCH'}
        if reader is None:
            from weex_live_worker import Reader
            reader=Reader(root)
        opened=reader.read('get_capi_v3_order',orderId=eid)
        closed=reader.read('get_capi_v3_order',orderId=closeid)
        fills=reader.read('get_capi_v3_userTrades',symbol=symbol,orderId=eid,limit=100)
        exits=reader.read('get_capi_v3_userTrades',symbol=symbol,orderId=closeid,limit=100)
        stops=reader.read('get_capi_v3_allAlgoOrders',symbol=symbol)
        positions,orders,algos=reader.account()
        # Certification is scoped to the exact production entry symbol.
        # Foreign manual positions are not close targets, but their account
        # exposure remains visible to the separate CROSS entry guardian.
        from weex_supervised_ownership_scope_v11 import split_exact_symbol
        scoped=split_exact_symbol(positions,orders,algos,symbol=symbol)
        target_flat=(not scoped['targetPositions'] and
                     not scoped['targetRegular'] and not scoped['targetConditional'])
        matching=[x for x in stops.get('orders',[]) if str(x.get('algoId'))==stopid] if isinstance(stops,dict) else []
        stop=matching[0] if len(matching)==1 else {}
        good=(isinstance(opened,dict) and opened.get('clientOrderId')==cid and
            str(opened.get('orderId'))==eid and opened.get('status')=='FILLED' and
            opened.get('symbol')==symbol and opened.get('positionSide')==plan.get('positionSide') and
            opened.get('side')==plan.get('side') and money(opened.get('executedQty'))==qty and
            isinstance(closed,dict) and str(closed.get('orderId'))==closeid and
            closed.get('status')=='FILLED' and closed.get('reduceOnly') is True and
            closed.get('symbol')==symbol and closed.get('positionSide')==plan.get('positionSide') and
            closed.get('side')==('SELL' if plan.get('side')=='BUY' else 'BUY') and
            money(closed.get('executedQty'))==qty and
            _one_fill(fills,eid,qty,opened.get('side')) and
            _one_fill(exits,closeid,qty,closed.get('side')) and
            len(matching)==1 and stop.get('algoStatus') in ('CANCELED','CANCELLED','FILLED') and
            stop.get('symbol')==symbol and stop.get('positionSide')==plan.get('positionSide') and
            stop.get('side')==closed.get('side') and stop.get('orderType')=='STOP_MARKET' and
            stop.get('reduceOnly') is True and stop.get('clientAlgoId')==cid+'sl' and
            str(stop.get('actualOrderId'))==eid and money(stop.get('quantity'))==qty and
            target_flat)
        return {'certified':good,'reason':'REAL_WORKER_CRASH_VERIFIED' if good else 'INDEPENDENT_EXCHANGE_PROOF_FAILED',
            'scope':SCOPE,'exchangeWrites':0}
    except Exception as exc:
        return {'certified':False,'reason':'PROOF_READ_FAILED_'+type(exc).__name__}

if __name__=='__main__':
    print(json.dumps(certify()))
