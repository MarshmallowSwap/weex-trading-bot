"""Production-worker-only ETHUSDT CROSS100 protected entry ACK crash child.

This module is NOT a standalone live trigger: the production worker script
must explicitly invoke run_child(), after completed release-specific safety
checks. The one real entry uses production Lifecycle durable UNKNOWN, a scoped
SDK transport and an independent one-shot permit, not the general GO switch.
If HTTP ACK succeeds, os._exit(79) occurs before the SQLite ACK is persisted.
Never invoke without an independently active recovery supervisor.
"""
from __future__ import annotations
import copy,hashlib,json,os,sys,time
from decimal import Decimal as D
from pathlib import Path
from urllib.parse import urlsplit
from weex_supervised_crash_executor_v2 import (
    CLIENT_ID,SIGNAL_ID,validate_scope,Blocked,QUANTITY,NOTIONAL_CAP)
from weex_supervised_one_shot_permission_v4 import authorize_once
from weex_supervised_entry_permit_v5 import check_and_consume
ROOT=Path(__file__).resolve().parent
HOST='https://api-contract.weex.com'
OP='post_capi_v3_order'
PERMIT=ROOT/'weex_supervised_crash_trial_v5_permit.sqlite3'

def process_alive(pid):
    """Use OS-native PID liveness instead of optional psutil dependency."""
    pid=int(pid)
    if pid<=0 or pid==os.getpid():
        return False
    if sys.platform=='win32':
        import ctypes
        from ctypes import wintypes
        k=ctypes.WinDLL('kernel32',use_last_error=True)
        k.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD]
        k.OpenProcess.restype=wintypes.HANDLE
        k.GetExitCodeProcess.argtypes=[wintypes.HANDLE,ctypes.POINTER(wintypes.DWORD)]
        k.GetExitCodeProcess.restype=wintypes.BOOL
        k.CloseHandle.argtypes=[wintypes.HANDLE]
        k.CloseHandle.restype=wintypes.BOOL
        handle=k.OpenProcess(0x1000,False,pid) # PROCESS_QUERY_LIMITED_INFORMATION
        if handle:
            try:
                exitcode=wintypes.DWORD(0)
                return bool(k.GetExitCodeProcess(handle,ctypes.byref(exitcode))
                            and exitcode.value==259) # STILL_ACTIVE
            finally:
                k.CloseHandle(handle)
        # S4U tasks run in session 0; an unelevated but same-user observer
        # can enumerate the PID although OpenProcess is ACCESS_DENIED.
        # Validate native tasklist CSV exactly: no substring/PID matching.
        import subprocess,csv,io
        try:
            cp=subprocess.run(['tasklist.exe','/FI','PID eq '+str(pid),
                               '/FO','CSV','/NH'],
                              capture_output=True,text=True,timeout=4,
                              creationflags=0x08000000)
            if cp.returncode!=0:return False
            return any(len(row)>=2 and row[0].casefold() in
                       ('python.exe','pythonw.exe') and row[1]==str(pid)
                       for row in csv.reader(io.StringIO(cp.stdout)))
        except (OSError,subprocess.TimeoutExpired,UnicodeError,csv.Error):
            return False
    try:
        os.kill(pid,0)
        return True
    except (ProcessLookupError,PermissionError,OSError):
        return False

def supervisor_ready(root=ROOT):
    """A running independent supervisor must have renewed its own heartbeat."""
    try:
        h=json.loads((Path(root)/'weex_supervised_crash_supervisor_health.json').read_text(encoding='utf-8'))
        if (h.get('status')!='READY_TO_RECOVER' or
            h.get('scope')!='ETH100_CRASH_PRODUCTION_WORKER_V5' or
            h.get('supportsExactReduceOnlyClose') is not True or
            h.get('hasIndependentRestartTask') is not True or
            not 0<=time.time()-float(h['heartbeatEpoch'])<=8):
            return False
        # Verify PID liveness with native OS API, not an optional dependency.
        return process_alive(h['pid'])
    except (OSError,ValueError,KeyError,TypeError,ImportError):
        return False

def fresh_capture(root=ROOT,reader=None):
    """Fresh authenticated exchange preflight including real strategy guard."""
    import live_control
    from weex_live_worker import Reader,capture,SCOPE
    from weex_simple_bot import public
    from orderbook_liquidity import inspect
    from weex_api_budget import Budget
    root=Path(root)
    config=json.loads((root/'weex_ai_risk_config.json').read_text(encoding='utf-8'))
    if (live_control.state(root)['mode']!='STOPPED' or live_control.build_errors(root)
        or config['risk']['minimumLeverage']!=100
        or config['execution']['enabled'] is not False
        or config['execution']['mode']!='PRETRADE'):
        raise Blocked('STOPPED_INTEGRITY_100X_REQUIRED')
    if not supervisor_ready(root):raise Blocked('INDEPENDENT_SUPERVISOR_NOT_READY')
    # Reserve 150 weight for independent recovery/exit, plus an estimated
    # 100-weight capture allowance. Check all WEEX server windows, not a
    # hardcoded admission threshold on the trailing 600-second total.
    Budget(root).require_supervised_recovery_headroom(preflight_weight=100)
    r=reader if reader is not None else Reader(root)
    pos,orders,algos=r.account()
    if pos or orders or algos:raise Blocked('ACCOUNT_NOT_FLAT')
    metadata=public('/capi/v3/market/exchangeInfo',symbol='ETHUSDT')
    contract=next(x for x in metadata['symbols'] if x['symbol']=='ETHUSDT')
    risk=public('/capi/v3/market/riskLimits',symbol='ETHUSDT')
    tiers=next(x['brackets'] for x in risk if x['symbol']=='ETHUSDT')
    settings=r.read('get_capi_v3_account_symbolConfig',symbol='ETHUSDT')
    book=inspect('ETHUSDT')
    scoped=validate_scope(config=config,contract=contract,tiers=tiers,settings=settings,
        book=book,account={'complete':True,'flat':True,'recoveryClear':True,'noUnresolvedWrites':True})
    from weex_live_worker import capture
    plan,ctx,signal=capture(r,'ETHUSDT',config,manual_side='LONG')
    if ctx['positions'] or ctx['openOrders'] or ctx['conditionalOrders']:
        raise Blocked('FRESH_ENTRY_CONTEXT_NOT_FLAT')
    price=D(str(ctx['referencePrice']))
    if price<=0 or price*QUANTITY>NOTIONAL_CAP:
        raise Blocked('LIVE_PRICE_OUTSIDE_SMALL_NOTIONAL')
    payload=scoped['payload']
    if payload['newClientOrderId']!=CLIENT_ID or D(payload['quantity'])!=QUANTITY:
        raise Blocked('ONE_SHOT_PAYLOAD_CHANGED')
    stop=D(payload['slTriggerPrice'])
    if not 0<(price-stop)/price<=D('0.005'):
        raise Blocked('STOP_CHANGED_RELATIVE_TO_FRESH_PRICE')
    # Bind this isolated supervised pilot to the same immutable production
    # scope that Gateway.validate checks, without enabling normal dispatch.
    plan.update(entrySource='supervised_crash_pilot',
        liveAuthorizationScope=SCOPE,
        pilotReferencePrice=str(price),beforePositions=[],
        requestedLeverage='100')
    plan['orderPreview'].update(payload)
    plan['sizing']['quantity']=str(QUANTITY)
    plan['sizing']['notionalUSDT']=str(price*QUANTITY)
    plan['requiredMarginAndEntryFeeUSDT']=str(
        price*QUANTITY*(D('0.01')+D(str(ctx['exitFeeRate']))))
    ctx['maximumPermittedLeverage']='100'
    if ctx['availableBalance'] is None or D(str(ctx['availableBalance']))<D('5'):
        raise Blocked('MINIMUM_ACCOUNT_BALANCE_NOT_CONFIRMED')
    # Capture consumed quota. Reassess the actual remaining emergency reserve
    # before handing the plan to any entry authority.
    Budget(root).require_supervised_recovery_headroom()
    cfg,digest=live_control.configuration(root)
    plan['authorization']={'host':HOST,'generation':live_control.state(root)['generation'],'configHash':digest}
    return plan,ctx,config,payload,r

class PilotTransport:
    """One actual POST /capi/v3/order; only exact native-stop ENTRY accepted."""
    def __init__(self,payload,root=ROOT):
        self.payload=payload;self.root=Path(root);self.calls=0
        import requests
        self.session=requests.Session()
    def request(self,method,url,**kw):
        u=urlsplit(url)
        if (self.calls or method!='POST' or u.scheme!='https'
            or u.netloc!='api-contract.weex.com' or u.path!='/capi/v3/order'
            or u.query or u.fragment or kw.get('json') is not None or kw.get('params')
            or json.loads(kw.get('data') or '{}')!=self.payload):
            raise PermissionError('PILOT_UNSCOPED_OR_DUPLICATE_POST')
        self.calls+=1
        if not supervisor_ready(self.root):
            raise PermissionError('SUPERVISOR_NOT_READY_AT_HTTP_DISPATCH')
        # Check emergency readback/close capacity again at the dispatch edge.
        from weex_api_budget import Budget
        Budget(self.root).require_supervised_recovery_headroom()
        check_and_consume(root=self.root,permit_db=PERMIT,payload=self.payload)
        from weex_api_budget import request as budget_request
        kw['allow_redirects']=False
        response=budget_request(self.session,method,url,**kw)
        if response.status_code!=200:
            raise RuntimeError('PILOT_REAL_ENTRY_OUTCOME_UNKNOWN')
        return response
    def close(self):self.session.close()

class PilotGateway:
    """Exactly one pilot ENTRY, uses same production Lifecycle journal."""
    def __init__(self,root,reader,ctx):
        self.root=Path(root);self.reader=reader;self.ctx=ctx
        self.engine=None;self.current=None
    def write(self,operation,payload):
        from weex_live_worker import Gateway
        # Gateway.validate executes the normal worker's full entry guard.
        Gateway.validate(self,operation,payload)
        if operation!=OP or payload.get('newClientOrderId')!=CLIENT_ID:
            raise PermissionError('PILOT_ONLY_ENTRY')
        from weex_http_guard import sdk_types
        sdk,contract,ops=sdk_types()
        transport=PilotTransport(payload,self.root)
        try:
            cred=json.loads((self.root/'weex_credentials.json').read_text(encoding='utf-8'))
            api=contract(config_rest_api=sdk(base_path=HOST,api_key=cred['api_key'],
                api_secret=cred['secret_key'],passphrase=cred['passphrase'],
                session=transport,max_retries=0,timeout=10))
            response=api.rest_api.execute_operation(OP,{'body':payload})
            if (response.status_code!=200 or not isinstance(response.data,dict)
                or response.data.get('success') is not True
                or not response.data.get('orderId')
                or response.data.get('clientOrderId')!=CLIENT_ID):
                raise RuntimeError('REAL_ENTRY_ACK_UNVERIFIED')
            return response.data
        finally:transport.close()
    def read(self,*args,**kwargs):
        raise PermissionError('PILOT_GATEWAY_WRITE_PHASE_NO_READ')
    def _test_crash_after_entry_ack(self,trade_id,op,payload,response):
        if (trade_id!=CLIENT_ID or op!=OP or
            response.get('clientOrderId')!=CLIENT_ID or not response.get('orderId')):
            raise PermissionError('CRASH_OUTCOME_NOT_EXACT')
        os._exit(79)

def run_child(root=ROOT, *, external_approval=None, independent_evidence=None):
    """Fail closed unless a separate supervisor supplies exact approval and independently observed evidence."""
    from weex_live_worker import Lifecycle
    from weex_capacity import account_capacity
    root=Path(root)
    # Do not allow CLI direct imports to cause any exchange write.
    if Path(sys.argv[0]).name!='weex_live_worker.py' or '--supervised-crash-child' not in sys.argv:
        raise PermissionError('ACTUAL_WORKER_PROCESS_REQUIRED')
    if not callable(external_approval) or not callable(independent_evidence):
        raise PermissionError('INDEPENDENT_EXACT_APPROVAL_AND_EVIDENCE_REQUIRED')
    plan,ctx,cfg,payload,reader=fresh_capture(root)
    x=copy.deepcopy(cfg);x['execution'].update(enabled=True,mode='LIVE')
    gateway=PilotGateway(root,reader,ctx)
    engine=Lifecycle(root/'weex_user_live_lifecycle.sqlite3',gateway,lambda:x)
    gateway.engine=engine
    item=engine.prepare(SIGNAL_ID,plan)
    gateway.current=item['id']
    if item['id']!=CLIENT_ID or item['plan']['entry']!=payload:
        raise PermissionError('ACTUAL_JOURNAL_ENTRY_NOT_EXACT')
    engine.guard(item,ctx)
    context=independent_evidence(payload,ctx)
    if not isinstance(context,dict):
        raise PermissionError('INDEPENDENT_CONTEXT_INVALID')
    # Evidence must be generated by the separate supervisor. The child cannot
    # self-assert readiness flags or turn a user's general request into approval.
    decision=external_approval(payload,context)
    if decision is not True:
        raise PermissionError('EXACT_PILOT_OPERATION_NOT_APPROVED')
    authorize_once(PERMIT,payload,approval=decision,context=context)
    # This appends actual production Lifecycle durable UNKNOWN before HTTP.
    # Successful exchange ACK triggers os._exit(79), never returns normally.
    # A hard-coded capacity=0 is not an exchange observation.
    # Re-read the actual account immediately before the durable send boundary;
    # the HTTP transport will still independently validate and consume the
    # one-shot permission, and no account uncertainty permits a new entry.
    fresh_positions,fresh_regular,fresh_conditional=reader.account()
    if fresh_positions or fresh_regular or fresh_conditional:
        raise PermissionError('PILOT_ACCOUNT_CHANGED_AFTER_APPROVAL')
    cap=account_capacity(fresh_positions,fresh_regular+fresh_conditional)
    if cap.get('count')!=0 or cap.get('symbols')!=[]:
        raise PermissionError('PILOT_CAPACITY_NOT_FLAT')
    result=engine.send_once(item['id'],'ENTRY',OP,payload,capacity=cap)
    raise RuntimeError('PILOT_ENTRY_NOT_CRASHED_AFTER_ACK_'+str(result.get('state')))
