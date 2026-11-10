"""Read-only, fail-closed release prerequisites for the exact ETH crash trial.

No exchange GET/POST, no grants, no state mutation. Fresh account evidence
is required and all cross-margin positions remain in the veto, even manual.
"""
from pathlib import Path
import json,time
from weex_account_observation import load
from weex_supervised_crash_entry_child_v5 import supervisor_ready
ROOT=Path(__file__).resolve().parent

def evaluate(capabilities, snapshot, *, supervisor_ready_confirmed=False):
 reasons=[]
 if not isinstance(capabilities,dict):
  return {'admissible':False,'blockers':['CAPABILITIES_NOT_AVAILABLE'],
          'writes':0,'mayGrantPermit':False}
 for key,reason in (
  ('taskS4UVerified','S4U_RESTART_NOT_VERIFIED'),
  ('supervisorHeartbeatLive','HEARTBEAT_NOT_VERIFIED'),
  ('productionIntegrityPass','BUILD_INTEGRITY_NOT_VERIFIED'),
  ('reduceOnlySdkPreviewPass','REDUCEONLY_SERIALIZATION_NOT_VERIFIED'),
  ('apiHeadroomReady','API_HEADROOM_INSUFFICIENT')):
  if capabilities.get(key) is not True:reasons.append(reason)
 if supervisor_ready_confirmed is not True:
  reasons.append('SUPERVISOR_NOT_READY_TO_RECOVER')
 if not isinstance(snapshot,dict) or snapshot.get('complete') is not True:
  reasons.append('FRESH_ACCOUNT_SNAPSHOT_MISSING')
 else:
  rows=[snapshot.get(k) for k in ('positions','regularOrders',
                                  'conditionalOrders','trailingOrders')]
  if any(not isinstance(v,list) for v in rows):
   reasons.append('ACCOUNT_ROWS_INCOMPLETE')
  elif any(rows):
   reasons.append('SHARED_CROSS_ACCOUNT_NOT_FLAT')
 # Permit is deliberately not granted here: only an explicit operator action,
 # bounded to an independently verified exact exit operation, can grant it.
 if capabilities.get('exitPermitActive') is not True:
  reasons.append('EXACT_EXIT_PERMIT_NOT_AUTHORIZED')
 return {'admissible':not reasons,'blockers':reasons,'writes':0,
         'mayGrantPermit':False,'liveReleaseCertified':False}

def check(root=ROOT):
 from weex_independent_recovery_capability_v14 import check as capability_check
 root=Path(root)
 caps=capability_check(root)
 snapshot=load(root,max_age=10)
 ready=supervisor_ready(root)
 result=evaluate(caps,snapshot,supervisor_ready_confirmed=ready)
 result['status']='EXACT_LIVE_CRASH_TRIAL_PREREQUISITES_ONLY'
 result['mainTradingArmed']=False
 return result

if __name__=='__main__':
 print(json.dumps(check(),ensure_ascii=False))
