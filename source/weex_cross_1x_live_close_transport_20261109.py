"""LIVE-capable, but separately DISARMED, supervised exact-position WEEX close.

This is exit-only. It never opens positions, kills processes, starts the bot
or retries an uncertain POST. The real network path is unreachable until:
- exact scope from fresh authenticated WEEX GET confirms CROSS 1x and native SL
- Telegram grant for that exact position was consumed, once
- matching durable close dispatch already committed OUTCOME_UNKNOWN
- explicit separate emergency-close configuration switch is enabled.
Default DRY_RUN uses no credentials and refuses non-simulated sessions.
"""
import json,sqlite3
from pathlib import Path
from contextlib import closing
import live_control
from weex_pilot_emergency_close_sdk import (
  exact_payload,preview_position_close,exact_position_sdk_fields,OP,HOST)
from weex_cross_1x_close_sdk_adapter_20261109 import Cross1xCloseAdapter
from weex_cross_1x_operator_telegram_20261109 import current_scope,AUTH
from weex_cross_1x_single_use_approval_20261109 import fingerprint
from weex_cross_1x_supervised_executor_20261109 import get_record

class SupervisedCrossLiveClose:
 def __init__(self,root,*,pilot_id,mode='DRY_RUN',session_factory=None,reader=None):
  self.root=Path(root);self.pilot_id=pilot_id;self.mode=mode
  self.session_factory=session_factory;self.reader=reader;self.used=False
  if mode not in ('DRY_RUN','LIVE'):
   raise PermissionError('INVALID_CLOSE_MODE')
  if not isinstance(pilot_id,str) or not pilot_id.startswith('wxpilot_'):
   raise PermissionError('INVALID_PILOT_ID')
 def __call__(self,operation,payload):
  if self.used:raise PermissionError('LIVE_CLOSE_ONE_REQUEST_ONLY')
  if operation!=OP or not isinstance(payload,dict) or payload!=exact_payload(payload.get('positionId')):
   raise PermissionError('INVALID_EXACT_CLOSE_REQUEST')
  if live_control.state(self.root)['mode']!='STOPPED' or live_control.build_errors(self.root):
   raise PermissionError('MAIN_BOT_NOT_SAFE')
  scope=current_scope(self.root,self.reader)
  if scope['pilotId']!=self.pilot_id or scope['payload']!=payload:
   raise PermissionError('FRESH_EXCHANGE_SCOPE_CHANGED')
  journal=get_record(self.root/'weex_cross_1x_supervised_close.sqlite3',self.pilot_id)
  if not (journal and journal['status']=='OUTCOME_UNKNOWN'
      and journal['position_id']==scope['positionId']
      and journal['entry_order_id']==scope['entryOrderId']
      and journal['stop_algo_id']==scope['stopAlgoId']
      and json.loads(journal['payload'])==payload):
   raise PermissionError('DURABLE_CLOSE_RESERVATION_MISSING_OR_CHANGED')
  authdb=self.root/AUTH
  if not authdb.is_file():raise PermissionError('TELEGRAM_APPROVAL_DATABASE_MISSING')
  with closing(sqlite3.connect('file:'+authdb.resolve().as_posix()+'?mode=ro',uri=True)) as c:
   c.execute('PRAGMA query_only=ON')
   proof=c.execute('''SELECT state,expires_at FROM cross_close_authorization_v1
       WHERE digest=? AND pilot_id=? AND position_id=?''',
       (fingerprint(scope),self.pilot_id,scope['positionId'])).fetchone()
  if not proof or proof[0]!='CONSUMED':
   raise PermissionError('SINGLE_USE_TELEGRAM_APPROVAL_NOT_CONSUMED')
  from datetime import datetime,timezone
  try:
   deadline=datetime.fromisoformat(proof[1])
   if deadline.tzinfo is None or deadline<=datetime.now(timezone.utc):
    raise PermissionError('SINGLE_USE_TELEGRAM_APPROVAL_EXPIRED')
  except (ValueError,TypeError):
   raise PermissionError('SINGLE_USE_TELEGRAM_APPROVAL_EXPIRY_INVALID')
  if self.mode=='DRY_RUN':
   if not self.session_factory:
    raise PermissionError('DRY_RUN_SESSION_REQUIRED')
   self.used=True
   adapter=Cross1xCloseAdapter(session_factory=self.session_factory)
   return adapter(operation,payload)
  config=json.loads((self.root/'weex_live_1x_pilot_config.json').read_text(encoding='utf-8'))
  if not (config.get('exchange')=='WEEX' and config.get('marginMode')=='CROSS'
      and config.get('leverage')==1 and config.get('maxNewOrders')==1
      and config.get('executionEnabled') is False
      and config.get('requireExplicitTestOrderApproval') is True
      and config.get('supervisedEmergencyCloseAllowed') is True):
   raise PermissionError('SUPERVISED_CROSS_CLOSE_NOT_ARMED')
  if not preview_position_close(payload):raise PermissionError('INVALID_SDK_CLOSE_SERIALIZATION')
  from weex_http_guard import sdk_types
  configuration,contract,operations=sdk_types()
  if operations[OP]['method']!='POST' or operations[OP]['path']!='/capi/v3/closePositions':
   raise PermissionError('EXACT_ENDPOINT_SPEC_MISMATCH')
  # Credentials used only after every safety gate passes. No hidden retry.
  creds=json.loads((self.root/'weex_credentials.json').read_text(encoding='utf-8'))
  owner=self
  class StrictSession:
   used=False
   def request(self,method,url,**kwargs):
    if self.used or method!='POST' or url!=HOST+'/capi/v3/closePositions':
     raise PermissionError('CLOSE_HTTP_METHOD_OR_ENDPOINT_CHANGED')
    if (kwargs.get('json') is not None or kwargs.get('params') or
        json.loads(kwargs.get('data') or b'{}')!=payload):
     raise PermissionError('UNEXPECTED_CLOSE_BODY')
    self.used=True;owner.used=True
    from weex_api_budget import budget,recovery
    with recovery():budget().reserve(method,url)
    session=owner.session_factory() if owner.session_factory else __import__('requests').Session()
    try:
     kwargs['allow_redirects']=False
     return session.request(method,url,**kwargs)
    finally:
     if hasattr(session,'close'):session.close()
   def close(self):pass
  with exact_position_sdk_fields() as (configuration,contract,operations):
   client=contract(config_rest_api=configuration(base_path=HOST,
      api_key=creds['api_key'],api_secret=creds['secret_key'],
      passphrase=creds['passphrase'],session=StrictSession(),
      max_retries=0,timeout=10))
   result=client.rest_api.execute_operation(OP,payload)
  if result.status_code!=200 or not isinstance(result.data,list) or len(result.data)!=1:
   raise RuntimeError('CLOSE_ACK_UNCERTAIN')
  row=result.data[0]
  if (row.get('success') is not True or str(row.get('positionId'))!=str(payload['positionId'])
      or not row.get('successOrderId')):
   raise RuntimeError('CLOSE_ACK_INCOMPLETE')
  return {'success':True,'positionId':str(row['positionId']),
          'orderId':str(row['successOrderId'])}
