"""Scoped real-capable MARKET reduceOnly exit for a single proven ETH100 crash pilot.

Default entry point does not transmit. Exactly one outbound close POST is possible
after independent journal/exchange proof and external exact-operation approval.
On any uncertain outcome the durable record forbids another POST.
Never sends entry orders, cancels stops or operates the production switch.
"""
from __future__ import annotations
import json,sqlite3,time
from contextlib import closing
from pathlib import Path
from urllib.parse import urlsplit
from weex_supervised_reduce_only_close_plan_v4 import compose
from weex_supervised_real_recovery_v3 import read_exchange
from weex_http_guard import sdk_types
from weex_api_budget import request as budget_request
import live_control

ROOT=Path(__file__).resolve().parent
STATE='weex_supervised_reduceonly_close_v4.sqlite3'
OP='post_capi_v3_order'
HOST='https://api-contract.weex.com'
class CloseDenied(RuntimeError):pass

def reserve(root,client_id,payload):
    db=Path(root)/STATE
    with closing(sqlite3.connect(db,timeout=8)) as con:
        con.execute('PRAGMA busy_timeout=8000')
        con.execute('CREATE TABLE IF NOT EXISTS intents (entry TEXT PRIMARY KEY,'
                    'payload TEXT NOT NULL,status TEXT NOT NULL,created REAL NOT NULL)')
        con.execute('BEGIN IMMEDIATE')
        if con.execute('SELECT 1 FROM intents WHERE entry=?',(client_id,)).fetchone():
            con.rollback()
            raise CloseDenied('CLOSE_ALREADY_RESERVED_NEVER_RESEND')
        con.execute('INSERT INTO intents VALUES(?,?,?,?)',
                    (client_id,json.dumps(payload,sort_keys=True),'OUTCOME_UNKNOWN',time.time()))
        con.commit()
    return db

def verify_conditions(root,client_id,r):
    cfg=json.loads((Path(root)/'weex_ai_risk_config.json').read_text(encoding='utf-8'))
    if live_control.state(root)['mode']!='STOPPED' or live_control.build_errors(root):
        raise CloseDenied('PRODUCTION_CONTROL_OR_HASH_INVALID')
    if cfg['execution'].get('enabled') is not False or cfg['execution'].get('mode')!='PRETRADE':
        raise CloseDenied('PRODUCTION_NOT_DISARMED')
    if cfg['risk']['minimumLeverage']!=100:raise CloseDenied('PILOT_LEVERAGE_SCOPE_CHANGED')
    proof=read_exchange(client_id,root=root,reader=r)
    positions,regular,conditional=r.account()
    setting=r.read('get_capi_v3_account_symbolConfig',symbol='ETHUSDT')
    preview=compose(proof=proof,positions=positions,
        regular_orders=regular,conditional_orders=conditional,settings=setting)
    if preview.get('status')!='CLOSE_PREVIEW_ONLY' or preview.get('networkRequests')!=0:
        raise CloseDenied('REDUCEONLY_PREVIEW_INCOMPLETE')
    return proof,preview['payload']

class OnlyReduceClose:
    def __init__(self,payload,session=None):
        self.payload=payload
        self.session=session
        self.calls=0
    def request(self,method,url,**kw):
        parsed=urlsplit(url)
        if (self.calls!=0 or method!='POST' or parsed.scheme!='https'
            or parsed.netloc!='api-contract.weex.com' or parsed.path!='/capi/v3/order'
            or parsed.query or parsed.fragment or kw.get('params') or kw.get('json') is not None
            or json.loads(kw.get('data') or '{}')!=self.payload):
            raise CloseDenied('UNSCOPED_OR_REPEATED_REDUCEONLY_POST')
        self.calls+=1
        if self.payload.get('side')!='SELL' or self.payload.get('positionSide')!='LONG' or self.payload.get('reduceOnly') is not True:
            raise CloseDenied('NOT_A_REDUCE_ONLY_CLOSE')
        kw['allow_redirects']=False
        if self.session is None:
            import requests
            self.session=requests.Session()
        response=budget_request(self.session,method,url,**kw)
        if response.status_code!=200:raise CloseDenied('CLOSE_HTTP_OUTCOME_UNKNOWN')
        return response
    def close(self):
        if self.session is not None:
            self.session.close()

def send_once(client_id,*,root=ROOT,reader=None,approval=None,session=None):
    """One actual exit POST, only after explicit exact-payload approval."""
    if not callable(approval):raise CloseDenied('EXTERNAL_CLOSE_APPROVAL_REQUIRED')
    root=Path(root)
    if (root/STATE).is_file():
        # A prior reservation exists: never assume it was not transmitted.
        with closing(sqlite3.connect(root/STATE)) as con:
            con.execute('PRAGMA query_only=ON')
            if con.execute('SELECT 1 FROM intents WHERE entry=?',(client_id,)).fetchone():
                raise CloseDenied('CLOSE_ALREADY_RESERVED_NEVER_RESEND')
    from weex_live_worker import Reader
    r=reader or Reader(root)
    proof,payload=verify_conditions(root,client_id,r)
    if approval(OP,payload,proof) is not True:raise CloseDenied('EXACT_REDUCEONLY_CLOSE_NOT_APPROVED')
    reserve(root,client_id,payload)
    # From here, no retry after timeout, OS crash or unexpected reply.
    transport=OnlyReduceClose(payload,session=session)
    try:
        sdk,Contract,ops=sdk_types()
        if ops[OP]['method']!='POST' or ops[OP]['path']!='/capi/v3/order':
            raise CloseDenied('WEEX_ORDER_ENDPOINT_MISMATCH')
        creds=json.loads((root/'weex_credentials.json').read_text(encoding='utf-8'))
        api=Contract(config_rest_api=sdk(base_path=HOST,api_key=creds['api_key'],
            api_secret=creds['secret_key'],passphrase=creds['passphrase'],
            session=transport,timeout=10,max_retries=0))
        result=api.rest_api.execute_operation(OP,{'body':payload})
        if result.status_code!=200 or not isinstance(result.data,dict):
            raise CloseDenied('CLOSE_ACK_UNVERIFIED')
        ack=result.data
        if ack.get('success') is not True or not ack.get('orderId'):
            raise CloseDenied('CLOSE_EXCHANGE_ACK_UNVERIFIED')
        return {'status':'CLOSE_ACK_READBACK_REQUIRED','closeOrderId':str(ack['orderId']),
            'retriesAllowed':False,'accountFlatVerified':False}
    finally:
        transport.close()

if __name__=='__main__':
    print(json.dumps({'status':'REDUCEONLY_CLOSE_TRANSPORT_INSTALLED',
     'realPOSTsSent':0,'defaultDispatchEnabled':False,
     'independentCloseAuditStillRequired':True}))
