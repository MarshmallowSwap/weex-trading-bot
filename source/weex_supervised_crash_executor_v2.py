"""WEEX supervised crash executor V2: offline OS-crash drill and GET-only readiness.

REAL ORDER SUBMISSION IS INTENTIONALLY NOT IMPLEMENTED.
No API keys are loaded, no writable exchange client is instantiated and no
production switch or release evidence is touched. A separate certified
production adapter is mandatory before a real test can be considered.
"""
from __future__ import annotations
import argparse,hashlib,json,os,sqlite3,subprocess,sys,tempfile,time
from decimal import Decimal as D,ROUND_DOWN,InvalidOperation
from pathlib import Path
from datetime import datetime,timezone
from contextlib import closing

ROOT=Path(__file__).resolve().parent
SCOPE='WEEX_SUPERVISED_ETH100_STOP_CRASH_V2'
SYMBOL='ETHUSDT'
LEVERAGE=D('100')
QUANTITY=D('0.001')
NOTIONAL_CAP=D('5')
STOP_PCT=D('0.003') # preliminary test stop 0.3%, still not a guaranteed loss cap
# Same immutable ID derivation as production Lifecycle.prepare(signal_id).
SIGNAL_ID='supervised_crash_v2|ETHUSDT|one_shot_20261109'
CLIENT_ID='wxentry_'+hashlib.sha256(SIGNAL_ID.encode()).hexdigest()[:24]

class Blocked(RuntimeError):pass

def money(value):
    if isinstance(value,bool):raise Blocked('INVALID_DECIMAL')
    try:r=D(str(value))
    except (InvalidOperation,TypeError,ValueError):raise Blocked('INVALID_DECIMAL')
    if not r.is_finite() or r<=0:raise Blocked('INVALID_DECIMAL')
    return r

def validate_scope(*,config,contract,tiers,settings,book,account):
    if config['execution']['enabled'] is not False or config['execution']['mode']!='PRETRADE':
        raise Blocked('PRODUCTION_MUST_REMAIN_DISARMED')
    if config['risk']['minimumLeverage']!=100:
        raise Blocked('STRATEGY_MINIMUM_NOT_100')
    if (config['risk']['stopLoss']['enabled'] is not False):
        raise Blocked('UNEXPECTED_STRATEGY_STOP_CONFIGURATION')
    if contract.get('symbol')!=SYMBOL or money(contract['maxLeverage'])<LEVERAGE:
        raise Blocked('CONTRACT_100X_NOT_ELIGIBLE')
    if money(contract['minOrderSize'])!=QUANTITY:
        raise Blocked('MINIMUM_QUANTITY_CHANGED')
    step=D(10)**-int(contract['quantityPrecision'])
    if QUANTITY%step:raise Blocked('QUANTITY_STEP_MISMATCH')
    if (not isinstance(tiers,list) or not any(
        D(str(t['notionalFloor']))<=QUANTITY*money(book['bestAsk'])<money(t['notionalCap'])
        and money(t['initialLeverage'])>=LEVERAGE for t in tiers)):
        raise Blocked('PUBLIC_RISK_TIER_NOT_VERIFIED')
    if (not isinstance(settings,list) or len(settings)!=1 or
        settings[0].get('symbol')!=SYMBOL or
        settings[0].get('marginType') not in ('CROSS','CROSSED') or
        settings[0].get('separatedType')!='COMBINED' or
        money(settings[0].get('crossLeverage',0))!=LEVERAGE):
        raise Blocked('ACCOUNT_CROSS_100X_NOT_CONFIRMED')
    if book.get('symbol')!=SYMBOL or book.get('status')!='OK' or book.get('depthUnitVerified') is not True:
        raise Blocked('BOOK_NOT_VERIFIED')
    bid=money(book['bestBid']);ask=money(book['bestAsk'])
    if not bid<ask:raise Blocked('CROSSED_BOOK')
    if QUANTITY*ask>NOTIONAL_CAP:raise Blocked('MINIMUM_NOTIONAL_ABOVE_CAP')
    if (not isinstance(account,dict) or account.get('complete') is not True or
        account.get('flat') is not True or account.get('recoveryClear') is not True or
        account.get('noUnresolvedWrites') is not True):
        raise Blocked('ACCOUNT_RECOVERY_NOT_CLEAR')
    tick=D(10)**-int(contract['pricePrecision'])
    stop=((ask*(1-STOP_PCT))/tick).to_integral_value(rounding=ROUND_DOWN)*tick
    if stop<=0 or stop>=bid:raise Blocked('STOP_INVALID')
    payload={'symbol':SYMBOL,'side':'BUY','positionSide':'LONG',
        'type':'MARKET','quantity':format(QUANTITY,'f'),
        'newClientOrderId':CLIENT_ID,
        'slTriggerPrice':format(stop,'f'),'SlWorkingType':'MARK_PRICE'}
    from weex_http_guard import prepare_sdk_request
    check=prepare_sdk_request('post_capi_v3_order',payload)
    if check.get('state')!='STOPPED_BEFORE_NETWORK' or check.get('networkRequests')!=0 or check.get('sdkSerializationVerified') is not True:
        raise Blocked('SDK_STOP_SERIALIZATION_FAILED')
    return {'status':'READY_FOR_ISOLATED_OFFLINE_DRILL','symbol':SYMBOL,'quantity':format(QUANTITY,'f'),
        'leverage':'100','notionalUSDT':format(QUANTITY*ask,'f'),
        'indicativeInitialMarginUSDT':format(QUANTITY*ask/LEVERAGE,'f'),
        'attachedStop':format(stop,'f'),'stopWorkingType':'MARK_PRICE',
        'payload':payload,'ordersSent':0,'liveApproved':False,'maxLossGuaranteed':False}

def db_connect(path):
    c=sqlite3.connect(path,timeout=8)
    c.execute('PRAGMA busy_timeout=8000')
    c.execute('PRAGMA journal_mode=WAL')
    c.execute('CREATE TABLE IF NOT EXISTS intent(id TEXT PRIMARY KEY, status TEXT, payload TEXT, ack TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS exchange_order(id TEXT PRIMARY KEY, payload TEXT, status TEXT, stop TEXT, close_id TEXT)')
    return c

def reserve(path,payload):
    with closing(db_connect(path)) as c, c:
        c.execute('BEGIN IMMEDIATE')
        if c.execute('SELECT 1 FROM intent WHERE id=?',(CLIENT_ID,)).fetchone():
            return False
        c.execute('INSERT INTO intent VALUES(?,?,?,NULL)',(CLIENT_ID,'UNKNOWN',json.dumps(payload,sort_keys=True)))
        c.commit()
        return True

def fake_exchange_accepted(path,payload):
    with closing(db_connect(path)) as c, c:
        c.execute('BEGIN IMMEDIATE')
        row=c.execute('SELECT status,payload FROM intent WHERE id=?',(CLIENT_ID,)).fetchone()
        if not row or row[0]!='UNKNOWN' or json.loads(row[1])!=payload:
            raise Blocked('DURABLE_INTENT_MISSING_OR_CHANGED')
        if c.execute('SELECT 1 FROM exchange_order WHERE id=?',(CLIENT_ID,)).fetchone():
            raise Blocked('DUPLICATE_EXCHANGE_ORDER')
        if (payload.get('symbol')!=SYMBOL or payload.get('quantity')!='0.001'
            or payload.get('SlWorkingType')!='MARK_PRICE' or not payload.get('slTriggerPrice')):
            raise Blocked('UNPROTECTED_FAKE_ENTRY')
        c.execute('INSERT INTO exchange_order VALUES(?,?,?,?,NULL)',
          (CLIENT_ID,json.dumps(payload,sort_keys=True),'FILLED',payload['slTriggerPrice']))
        c.commit()
    return {'success':True,'orderId':'SIM-'+CLIENT_ID}

def child(path,payload):
    if not reserve(path,payload):raise Blocked('PREVIOUS_INTENT_NO_RETRY')
    ack=fake_exchange_accepted(path,payload)
    if ack.get('success') is not True:raise Blocked('FAKE_ACK_FAILED')
    # Real OS-level process death in test child, after fake exchange accept,
    # before writing ACK to the intent journal.
    os._exit(79)

def recover_no_retry(path,expected_payload):
    with closing(db_connect(path)) as c, c:
        intent=c.execute('SELECT status,payload,ack FROM intent WHERE id=?',(CLIENT_ID,)).fetchone()
        rows=c.execute('SELECT payload,status,stop,close_id FROM exchange_order WHERE id=?',(CLIENT_ID,)).fetchall()
        if not intent or intent[0]!='UNKNOWN' or intent[2] is not None:
            raise Blocked('PRE_ACK_UNKNOWN_NOT_DURABLE')
        if json.loads(intent[1])!=expected_payload:raise Blocked('INTENT_PAYLOAD_CHANGED')
        if len(rows)!=1:raise Blocked('AMBIGUOUS_EXCHANGE_READBACK')
        order,status,stop,close_id=rows[0]
        if (json.loads(order)!=expected_payload or status!='FILLED' or
            stop!=expected_payload['slTriggerPrice'] or close_id is not None):
            raise Blocked('EXCHANGE_ORDER_OR_STOP_MISMATCH')
        # No retry of entry is performed; simulation closes exact recorded order.
        close='SIM-CLOSE-'+CLIENT_ID
        with c:
            count=c.execute('UPDATE exchange_order SET status=?,close_id=? WHERE id=? AND status=?',
                ('CLOSED',close,CLIENT_ID,'FILLED')).rowcount
            if count!=1:raise Blocked('CLOSE_UNCERTAIN')
        closed=c.execute('SELECT status,close_id FROM exchange_order WHERE id=?',(CLIENT_ID,)).fetchone()
        if closed!=('CLOSED',close):raise Blocked('CLOSE_NOT_VERIFIED')
        return {'recovered':'UNKNOWN_NO_RETRY','attachedStopVerified':True,
            'exactOrderCloseVerified':True,'duplicateOrders':0,'fakeEntryOrders':1,'fakeCloseOrders':1}

def drill():
    payload={'symbol':SYMBOL,'side':'BUY','positionSide':'LONG','type':'MARKET','quantity':'0.001',
        'newClientOrderId':CLIENT_ID,'slTriggerPrice':'2100.00','SlWorkingType':'MARK_PRICE'}
    with tempfile.TemporaryDirectory(prefix='weex-v2-offline-') as directory:
        path=Path(directory)/'drill.sqlite3'
        proc=subprocess.run([sys.executable,'-B',str(Path(__file__).resolve()),'--child',
            str(path),json.dumps(payload,separators=(',',':'))],
            capture_output=True,text=True,timeout=12)
        if proc.returncode!=79:raise Blocked('CRASH_EXIT_CODE_NOT_79')
        result=recover_no_retry(path,payload)
        try:
            child(path,payload)
            raise Blocked('REPLAY_WAS_ACCEPTED')
        except Blocked as exc:
            if str(exc)!='PREVIOUS_INTENT_NO_RETRY':raise
        return {'status':'OFFLINE_OS_CRASH_PASS','childExitCode':79,
            'productionOrderWrites':0,'networkRequests':0,
            'productionReleaseCertified':False,**result}

def live_readonly():
    import live_control
    from weex_live_worker import Reader
    from weex_simple_bot import public
    from orderbook_liquidity import inspect
    cfg=json.loads((ROOT/'weex_ai_risk_config.json').read_text(encoding='utf-8'))
    if live_control.state(ROOT)['mode']!='STOPPED' or live_control.build_errors(ROOT):
        return {'status':'BLOCKED_PRODUCTION_CONTROL'}
    # Require a recent independent reconciliation, not just a flat account GET.
    from live_release_gate import recent_operational_reconciliation
    try:
        audited=json.loads((ROOT/'account_reconciliation_point1_latest.json').read_text(encoding='utf-8'))
    except (OSError,ValueError):
        return {'status':'BLOCKED_ACCOUNT_RECONCILIATION_MISSING','ordersSent':0}
    if not recent_operational_reconciliation(audited,max_age_seconds=120):
        return {'status':'BLOCKED_ACCOUNT_RECONCILIATION_STALE','ordersSent':0}
    reader=Reader(ROOT)
    positions,orders,algos=reader.account()
    if positions or orders or algos:
        return {'status':'BLOCKED_ACCOUNT_NOT_EMPTY',
            'positionCount':len(positions),'orderCount':len(orders),'conditionalCount':len(algos)}
    meta=public('/capi/v3/market/exchangeInfo',symbol=SYMBOL)
    contract=next(x for x in meta['symbols'] if x['symbol']==SYMBOL)
    tier=public('/capi/v3/market/riskLimits',symbol=SYMBOL)
    brackets=next(x['brackets'] for x in tier if x['symbol']==SYMBOL)
    setting=reader.read('get_capi_v3_account_symbolConfig',symbol=SYMBOL)
    book=inspect(SYMBOL)
    try:
        response=validate_scope(config=cfg,contract=contract,tiers=brackets,
            settings=setting,book=book,account={'complete':True,'flat':True,
                'recoveryClear':True,'noUnresolvedWrites':True})
        response.pop('payload')
        response['status']='READ_ONLY_CHECKS_PASS_REAL_ADAPTER_NOT_AUTHORIZED'
        return response
    except Blocked as exc:
        return {'status':'BLOCKED','reason':str(exc),'ordersSent':0,'liveApproved':False}

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--drill',action='store_true')
    parser.add_argument('--read-only-preflight',action='store_true')
    parser.add_argument('--child',nargs=2)
    args=parser.parse_args()
    try:
        if args.child:
            child(Path(args.child[0]),json.loads(args.child[1]))
        elif args.drill:print(json.dumps(drill(),ensure_ascii=False))
        elif args.read_only_preflight:print(json.dumps(live_readonly(),ensure_ascii=False))
        else:print(json.dumps({'status':'EXECUTOR_V2_OFFLINE_ONLY',
            'realOrderTransportInstalled':False,'ordersSent':0}))
    except Exception as exc:
        print(json.dumps({'status':'BLOCKED','reason':type(exc).__name__,
            'detail':str(exc) if isinstance(exc,Blocked) else None,'ordersSent':0}))
        sys.exit(2)
