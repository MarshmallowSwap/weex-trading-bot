"""Real supervisor -> V5 worker authorization bridge; fail-closed by default.

This module does NOT grant permits or set supervisor readiness. Evidence is
derived from a separately running supervisor, a second authenticated account
readback and an existing unspent exact-close authorization. Callback shapes
match run_child() exactly. Never trust caller-injected readiness flags.
"""
from __future__ import annotations
import hashlib,json,time
from pathlib import Path
from decimal import Decimal as D
from weex_supervised_crash_executor_v2 import CLIENT_ID
from weex_supervised_one_shot_permission_v4 import exact_payload

ROOT=Path(__file__).resolve().parent
class BridgeBlocked(PermissionError):pass

def ready(root=ROOT,*,supervisor_check=None,exit_status=None):
 root=Path(root)
 from weex_supervised_crash_entry_child_v5 import supervisor_ready
 from weex_supervised_exit_policy_v7 import status
 if (supervisor_check or supervisor_ready)(root) is not True:
  return {'ready':False,'reason':'INDEPENDENT_SUPERVISOR_NOT_READY'}
 p=(exit_status or status)(root)
 if not isinstance(p,dict) or p.get('canClose') is not True:
  return {'ready':False,'reason':'EXACT_EXIT_AUTHORIZATION_MISSING'}
 return {'ready':True,'reason':'PRE_ENTRY_BRIDGE_CONDITIONS_MET'}

def independent_evidence(payload,ctx,*,root=ROOT,read_account=None,read_config=None,
                         supervisor_check=None,exit_status=None,now=None,
                         api_headroom_check=None):
 import live_control
 from weex_live_worker import Reader
 root=Path(root)
 gate=ready(root,supervisor_check=supervisor_check,exit_status=exit_status)
 if gate['ready'] is not True:raise BridgeBlocked(gate['reason'])
 raw=exact_payload(payload)
 if not isinstance(ctx,dict):raise BridgeBlocked('INVALID_CAPTURE_CONTEXT')
 if live_control.state(root)['mode']!='STOPPED' or live_control.build_errors(root):
  raise BridgeBlocked('PRODUCTION_NOT_STOPPED')
 r=Reader(root) if read_account is None or read_config is None else None
 positions,orders,algos=(read_account or r.account)()
 if not all(isinstance(x,list) for x in (positions,orders,algos)) or positions or orders or algos:
  raise BridgeBlocked('SECOND_INDEPENDENT_ACCOUNT_NOT_FLAT')
 settings=(read_config or (lambda:r.read('get_capi_v3_account_symbolConfig',symbol='ETHUSDT')))()
 if (not isinstance(settings,list) or len(settings)!=1
     or settings[0].get('symbol')!='ETHUSDT'
     or settings[0].get('marginType') not in ('CROSS','CROSSED')
     or str(settings[0].get('crossLeverage'))!='100'):
  raise BridgeBlocked('SECOND_INDEPENDENT_ACCOUNT_LEVERAGE_UNVERIFIED')
 price=D(str(ctx.get('referencePrice','0')))
 stop=D(str(payload['slTriggerPrice']))
 if not price.is_finite() or price<=0 or not D(0)<(price-stop)/price<=D('0.005'):
  raise BridgeBlocked('NATIVE_ATTACHED_STOP_OUT_OF_RANGE')
 # Pre-entry assertions are based on verifiable request serialization,
 # NOT on a future stop existing on the exchange or a future close fill.
 from weex_http_guard import prepare_sdk_request
 from weex_api_budget import Budget
 entry_preview=prepare_sdk_request('post_capi_v3_order',payload)
 close_payload={'symbol':'ETHUSDT','side':'SELL','positionSide':'LONG',
     'type':'MARKET','quantity':'0.001',
     'newClientOrderId':'wxclose_'+CLIENT_ID.split('_',1)[1],
     'reduceOnly':True}
 close_preview=prepare_sdk_request('post_capi_v3_order',close_payload)
 for preview in (entry_preview,close_preview):
  if (not isinstance(preview,dict) or preview.get('state')!='STOPPED_BEFORE_NETWORK'
      or preview.get('networkRequests')!=0
      or preview.get('sdkSerializationVerified') is not True):
   raise BridgeBlocked('ENTRY_OR_REDUCEONLY_CLOSE_SDK_NOT_VERIFIED')
 headroom=api_headroom_check or (lambda:Budget(root).require_supervised_recovery_headroom())
 if headroom() is not True:
  raise BridgeBlocked('RECOVERY_API_HEADROOM_NOT_VERIFIED')
 at=int((now or time.time)()*1000)
 return {'mainMode':'STOPPED','productionIntegrity':True,'accountFlat':True,
         'accountLeverage':'100','atomicStopVerified':True,
         'closePathValidated':True,'independentSupervisorReady':True,
         'nativeStopSerializationVerified':True,
         'reduceOnlyCloseSerializationVerified':True,
         'liveStopExistsVerified':False,'liveCloseFillVerified':False,
         'apiBudgetReady':True,'observedAtMs':at,
         'clientOrderId':CLIENT_ID,'payloadSha256':hashlib.sha256(raw.encode()).hexdigest(),
         'proofSource':'INDEPENDENT_SUPERVISOR_AND_SECOND_EXCHANGE_READBACK',
         'scope':'ETH100_CRASH_PRODUCTION_WORKER_V5'}

def external_approval(payload,evidence,*,root=ROOT,now=None):
 import live_control
 from weex_supervised_crash_entry_child_v5 import supervisor_ready
 from weex_supervised_exit_policy_v7 import status
 root=Path(root)
 try:raw=exact_payload(payload)
 except Exception:return False
 if not isinstance(evidence,dict):return False
 digest=hashlib.sha256(raw.encode()).hexdigest()
 now_ms=int((now or time.time)()*1000)
 return (evidence.get('clientOrderId')==CLIENT_ID
         and evidence.get('payloadSha256')==digest
         and evidence.get('proofSource')=='INDEPENDENT_SUPERVISOR_AND_SECOND_EXCHANGE_READBACK'
         and evidence.get('scope')=='ETH100_CRASH_PRODUCTION_WORKER_V5'
         and evidence.get('nativeStopSerializationVerified') is True
         and evidence.get('reduceOnlyCloseSerializationVerified') is True
         and evidence.get('apiBudgetReady') is True
         and type(evidence.get('observedAtMs')) is int
         and 0<=now_ms-evidence['observedAtMs']<=5000
         and live_control.state(root)['mode']=='STOPPED'
         and not live_control.build_errors(root)
         and supervisor_ready(root) is True
         and status(root).get('canClose') is True)

def run_connected(root=ROOT):
 """Invoked ONLY from the actual weex_live_worker.py CLI branch."""
 from weex_supervised_crash_entry_child_v5 import run_child
 gate=ready(root)
 if not gate['ready']:raise BridgeBlocked(gate['reason'])
 return run_child(root,
   external_approval=lambda payload,context:external_approval(payload,context,root=root),
   independent_evidence=lambda payload,ctx:independent_evidence(payload,ctx,root=root))

if __name__=='__main__':
 print(json.dumps({'status':'BRIDGE_DISARMED_UNTIL_INDEPENDENT_READY',
                   'entryAllowed':False,'networkWrites':0}))
