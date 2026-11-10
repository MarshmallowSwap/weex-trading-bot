"""WEEX CROSS 1x exact-position close SDK adapter, safety-locked by default.

Factory accepts only an explicitly injected transport session, never creates a
requests.Session or reads live credentials. Authentic SDK serialization is used
for DRY_RUN tests. LIVE send capability is deliberately unavailable until an
independently certified supervised release path is installed.
"""
import json
from pathlib import Path
from weex_pilot_emergency_close_sdk import (
 exact_payload,preview_position_close,exact_position_sdk_fields,OP,HOST)
class Cross1xCloseAdapter:
 def __init__(self,*,session_factory,credential_provider=None,mode='DRY_RUN'):
  if session_factory is None or not callable(session_factory):
   raise PermissionError('EXPLICIT_SESSION_FACTORY_REQUIRED')
  if mode!='DRY_RUN':raise PermissionError('LIVE_CLOSE_TRANSPORT_NOT_CERTIFIED')
  if credential_provider is not None:raise PermissionError('DRY_RUN_NO_LIVE_CREDENTIALS')
  self.session_factory=session_factory;self.mode=mode
  self.send_count=0
 def __call__(self,operation,payload):
  if operation!=OP or payload!=exact_payload(payload.get('positionId')):
   raise PermissionError('EXACT_POSITION_CLOSE_ONLY')
  if not preview_position_close(payload):
   raise PermissionError('SDK_SERIALIZATION_FAILED')
  if self.send_count!=0:raise PermissionError('TRANSPORT_ONE_SHOT_ALREADY_USED')
  from weex_http_guard import sdk_types
  config,contract,ops=sdk_types()
  if ops[OP]['method']!='POST' or ops[OP]['path']!='/capi/v3/closePositions':
   raise PermissionError('SDK_ENDPOINT_CHANGED')
  sess=self.session_factory()
  if not getattr(sess,'simulation_only',False):
   raise PermissionError('NON_SIMULATED_SESSION_BLOCKED')
  adapter=self
  class GuardSession:
   used=False
   def request(self,method,url,**kwargs):
    if self.used or method!='POST' or url!=HOST+'/capi/v3/closePositions':
     raise PermissionError('INVALID_EMERGENCY_ENDPOINT_OR_RETRY')
    if kwargs.get('json') is not None or kwargs.get('params') or json.loads(kwargs.get('data') or b'{}')!=payload:
     raise PermissionError('PAYLOAD_MISMATCH')
    self.used=True;adapter.send_count+=1
    kwargs['allow_redirects']=False
    return sess.request(method,url,**kwargs)
   def close(self):
    if hasattr(sess,'close'):sess.close()
  with exact_position_sdk_fields() as (config,contract,ops):
   client=contract(config_rest_api=config(base_path=HOST,api_key='DRYRUN',
    api_secret='DRYRUN',passphrase='DRYRUN',
    session=GuardSession(),max_retries=0,timeout=10))
   response=client.rest_api.execute_operation(OP,payload)
  if response.status_code!=200 or not isinstance(response.data,list) or len(response.data)!=1:
   raise RuntimeError('CLOSE_ACK_UNCERTAIN')
  row=response.data[0]
  if str(row.get('positionId'))!=str(payload['positionId']) or row.get('success') is not True or not row.get('successOrderId'):
   raise RuntimeError('CLOSE_ACK_INVALID')
  return {'success':True,'positionId':str(row['positionId']),
          'orderId':str(row['successOrderId'])}
