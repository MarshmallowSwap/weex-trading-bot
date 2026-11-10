"""WEEX V31: read-only staging of pre-entry vs post-crash evidence.

No account or exchange writes. No operator permit issuance, promotion, or gate
changes. The UNKNOWN journal is a post-crash requirement, never a pre-entry
condition. Explicitly retain CROSS account-wide veto.
"""
from pathlib import Path
import json
from weex_independent_recovery_capability_v14 import check as capabilities
from weex_exact_crash_trial_admission_v15 import check as live_admission
from weex_supervisor_promotion_policy_v16 import inspect as promotion
from weex_supervised_exit_policy_v7 import status as permit
ROOT=Path(__file__).resolve().parent
import live_control

def check(root=ROOT,cap_reader=None,trial_reader=None,prom_reader=None,permit_reader=None):
 root=Path(root)
 c=(cap_reader or capabilities)(root)
 a=(trial_reader or live_admission)(root)
 p=(prom_reader or promotion)(root)
 x=(permit_reader or permit)(root)
 before=[]
 if not c.get('taskS4UVerified') or not c.get('supervisorHeartbeatLive'):
  before.append('INDEPENDENT_WATCHDOG_NOT_OPERATIONAL')
 if not c.get('productionIntegrityPass'):before.append('CODE_OR_STOP_SWITCH_UNVERIFIED')
 if not c.get('reduceOnlySdkPreviewPass'):before.append('REDUCEONLY_SERIALIZATION_UNVERIFIED')
 if not c.get('apiHeadroomReady'):before.append('API_HEADROOM_NOT_VERIFIED')
 if x.get('canClose') is not True:before.append('SCOPED_OPERATOR_EXIT_PERMIT_NOT_GRANTED')
 if 'SHARED_CROSS_ACCOUNT_NOT_FLAT' in a.get('blockers',[]) or 'SHARED_CROSS_COLLATERAL_NOT_FLAT' in p.get('blockers',[]):
  before.append('MANUAL_CROSS_EXPOSURE_PRESENT')
 if any(x in a.get('blockers',[]) for x in ('FRESH_ACCOUNT_SNAPSHOT_MISSING','ACCOUNT_ROWS_INCOMPLETE')) or any(x in p.get('blockers',[]) for x in ('FRESH_CROSS_ACCOUNT_SNAPSHOT_REQUIRED','ACCOUNT_SNAPSHOT_EXPIRED','ACCOUNT_SNAPSHOT_INCOMPLETE')):
  before.append('FRESH_COMPLETE_CROSS_ACCOUNT_READ_REQUIRED')
  before.append('CROSS_OCCUPANCY_UNVERIFIED_FAIL_CLOSED')
 if 'SUPERVISOR_NOT_READY_TO_RECOVER' in a.get('blockers',[]) or 'VERIFIED_OPERATIONAL_PROMOTION_CONTROLLER_NOT_INSTALLED' in p.get('blockers',[]):
  before.append('PRODUCTION_SUPERVISOR_PROMOTION_CONTROLLER_NOT_ATTESTED')
 after=['POST_ACK_DURABLE_UNKNOWN_REAL_WORKER_ENTRY',
        'INDEPENDENT_EXACT_PROTECTED_STOP_READBACK',
        'TRUE_WORKER_RESTART_NO_ENTRY_RETRY',
        'SINGLE_REDUCEONLY_CLOSE_AND_EXCHANGE_FILL',
        'FINAL_FLAT_ETH_AND_STOP_TERMINATION_READBACK']
 return {'status':'STAGED_LIVE_TRIAL_NO_GO','preEntryBlockers':before,
  'postCrashCertificationsRequired':after,
  'durableUnknownMustExistBeforeEntry':False,
  'requiresFreshCrossAccountCheck':True,
  'manualPositionsExcludedFromRiskCheck':False,
  'supervisorReady':False,'operatorPermissionGrantedByThisTool':False,
  'exchangeWrites':0,'liveReleaseCertified':False}

if __name__=='__main__':
 print(json.dumps(check(),ensure_ascii=False))
