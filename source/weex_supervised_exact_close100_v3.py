"""One-shot real WEEX CLOSE-POSITION transport for a verified supervised entry.

Never creates entries, never closes by symbol/all, never retries unknown outcome.
Normal program import and CLI are read-only. Live use requires explicit,
externally approved exact ID + independent recovery certificate at call time.
"""
from __future__ import annotations
import json,sqlite3,time
from pathlib import Path
from contextlib import closing
from decimal import Decimal as D
from weex_pilot_emergency_close_sdk import exact_payload,preview_position_close
from weex_supervised_real_recovery_v3 import read_exchange
import live_control
ROOT=Path(__file__).resolve().parent
HOST='https://api-contract.weex.com'
OP='post_capi_v3_closePositions'

class CloseBlocked(RuntimeError):pass

def statepath(root):return Path(root)/'weex_supervised_close100_v3.sqlite3'

def reserve_close(db,entry_id,position_id):
 """Unknown before network: subsequent calls never submit again."""
 with closing(sqlite3.connect(db,timeout=10)) as c:
  c.execute('PRAGMA busy_timeout=10000')
  c.execute('CREATE TABLE IF NOT EXISTS close_intents(entry TEXT PRIMARY KEY,position TEXT,status TEXT,created REAL)')
  c.execute('BEGIN IMMEDIATE')
  existing=c.execute('SELECT position,status FROM close_intents WHERE entry=?',(entry_id,)).fetchone()
  if existing:
   c.rollback();raise CloseBlocked('CLOSE_ALREADY_RESERVED_NO_RETRY')
  c.execute('INSERT INTO close_intents VALUES(?,?,?,?)',(entry_id,str(position_id),'UNKNOWN',time.time()))
  c.commit()

def validate_exact(root,client_id,position_id,account,exchange_proof):
 root=Path(root)
 cfg=json.loads((root/'weex_ai_risk_config.json').read_text(encoding='utf-8'))
 if live_control.state(root)['mode']!='STOPPED' or live_control.build_errors(root):
  raise CloseBlocked('PRODUCTION_STOP_AND_HASH_REQUIRED')
 if cfg['risk']['minimumLeverage']!=100 or cfg['execution']['enabled'] is not False:
  raise CloseBlocked('PRODUCTION_PRETRADE_SCOPE_CHANGED')
 if not client_id.startswith('wxentry_') or exchange_proof.get('status')!='VERIFIED_PROTECTED_NEED_EXACT_CLOSE':
  raise CloseBlocked('INDEPENDENT_ENTRY_AND_STOP_PROOF_REQUIRED')
 if exchange_proof.get('clientOrderId')!=client_id or str(exchange_proof.get('positionId'))!=str(position_id):
  raise CloseBlocked('PROOF_NOT_BOUND_TO_POSITION')
 if exchange_proof.get('symbol')!='ETHUSDT' or D(str(exchange_proof['quantity']))!=D('0.001'):
  raise CloseBlocked('CLOSE_NOT_TEST_SCOPE')
 if not isinstance(account,tuple) or len(account)!=3:
  raise CloseBlocked('INVALID_ACCOUNT_READBACK')
 positions,orders,conditional=account
 if not isinstance(positions,list) or len(positions)!=1 or orders:
  raise CloseBlocked('ACCOUNT_NOT_EXACT_TEST_POSITION')
 position=positions[0]
 if (str(position.get('id'))!=str(position_id) or position.get('symbol')!='ETHUSDT'
    or position.get('side')!='LONG' or D(str(position.get('size','0')))!=D('0.001')):
  raise CloseBlocked('EXACT_POSITION_CHANGED')
 linked=[row for row in conditional if row.get('symbol')=='ETHUSDT']
 if len(linked)!=1 or str(linked[0].get('algoId'))!=str(exchange_proof.get('stopAlgoId')):
  raise CloseBlocked('EXCHANGE_STOP_CHANGED')
 payload=exact_payload(position_id)
 preview_position_close(payload)
 return payload

def close_one(client_id,position_id,*,root=ROOT,authorization=None,reader=None,session_factory=None):
 """Real single close POST only after external exact-operation approval."""
 root=Path(root)
 if not callable(authorization):raise CloseBlocked('EXTERNAL_EXACT_CLOSE_AUTHORIZATION_MISSING')
 # Independent authenticated reads are mandatory before a single close.
 from weex_live_worker import Reader
 r=reader if reader is not None else Reader(root)
 proof=read_exchange(client_id,root=root,reader=r)
 acct=r.account()
 payload=validate_exact(root,client_id,position_id,acct,proof)
 if authorization(OP,payload,proof) is not True:
  raise CloseBlocked('EXACT_CLOSE_NOT_APPROVED')
 reserve_close(statepath(root),client_id,position_id)
 # From here local UNKNOWN persists across any crash, no automatic retries.
 # Use SDK's exact positionId field patch without modifying global metadata.
 from weex_pilot_emergency_close_sdk import exact_position_sdk_fields
 from weex_http_guard import sdk_types
 from weex_api_budget import recovery,budget
 with exact_position_sdk_fields() as (config,contract,operations):
  spec=operations[OP]
  if spec['method']!='POST' or spec['path']!='/capi/v3/closePositions':
   raise CloseBlocked('CLOSE_ENDPOINT_CHANGED')
  class OneShot:
   used=False
   def request(self,method,url,**kwargs):
    if (self.used or method!='POST' or url!=HOST+'/capi/v3/closePositions'
       or kwargs.get('json') is not None or kwargs.get('params')
       or json.loads(kwargs.get('data') or b'{}')!=payload):
     raise CloseBlocked('UNEXPECTED_CLOSE_DISPATCH')
    self.used=True
    if authorization(OP,payload,proof) is not True:raise CloseBlocked('CLOSE_APPROVAL_REVOKED')
    import requests
    session=session_factory() if session_factory else requests.Session()
    try:
     kwargs['allow_redirects']=False
     with recovery():budget().reserve(method,url)
     response=session.request(method,url,**kwargs)
     budget().observe(response.status_code,response.headers)
     if response.status_code!=200:raise CloseBlocked('CLOSE_OUTCOME_UNKNOWN')
     return response
    finally:
     if not session_factory:session.close()
   def close(self):pass
  cred=json.loads((root/'weex_credentials.json').read_text(encoding='utf-8'))
  client=contract(config_rest_api=config(base_path=HOST,api_key=cred['api_key'],
   api_secret=cred['secret_key'],passphrase=cred['passphrase'],
   session=OneShot(),max_retries=0,timeout=10))
  reply=client.rest_api.execute_operation(OP,payload)
  if reply.status_code!=200:raise CloseBlocked('CLOSE_RESPONSE_UNCERTAIN')
  # Response means only ACK. External verifier still needs trade fills and flat account.
  return {'state':'CLOSE_ACK_UNVERIFIED','entryId':client_id,'positionId':str(position_id),
   'entryRetriesAllowed':False,'closeRetriesAllowed':False,
   'independentFlatAccountVerificationRequired':True}

if __name__=='__main__':
 print(json.dumps({'status':'EXACT_CROSS_100X_CLOSE_COMPONENT_INSTALLED',
  'defaultExecution':'DISABLED','entryWritesSupported':False,'realCloseSent':False,
  'liveTestCertified':False}))
