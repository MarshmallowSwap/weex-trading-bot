"""Evidence-based independent certification of WEEX API-SIM protected exit.

Authentic exchange GET readback + one-shot execution report + regression
tests support a DEMO certification. Never changes live execution or risk config.
"""
import json,os
from pathlib import Path
from datetime import datetime,timezone
import live_control

ROOT=Path(__file__).resolve().parent
def read(name):return json.loads((ROOT/name).read_text(encoding='utf-8'))
def certify():
 trial=read('weex_sim_active_stop_close_trial_20261109.json')
 audit=read('weex_sim_active_stop_close_independent_audit_20261109.json')
 reasons=[]
 if trial.get('host')!='https://api-sim.weex.com' or audit.get('host')!=trial.get('host'):
  reasons.append('SIM_HOST_NOT_CONFIRMED')
 if trial.get('stage')!='SIM_ACTIVE_STOP_CLOSE_VERIFIED':
  reasons.append('SIM_END_TO_END_NOT_VERIFIED')
 if not all(trial.get(k) is True for k in ('stopVerifiedBeforeClose','positionFlatVerified','reduceOnlyCloseVerified')):
  reasons.append('STOP_OR_CLOSE_PROOF_MISSING')
 if trial.get('stopCanceledBeforeClose') is not False or trial.get('stopCancellationPosts')!=0:
  reasons.append('STOP_CANCELLED_PREMATURELY')
 if trial.get('simEntryPosts')!=1 or trial.get('simClosePosts')!=1:
  reasons.append('SIM_ONE_SHOT_COUNT_INVALID')
 if not all(audit.get(k) is True for k in ('independentProofPass','entryMatched',
       'closeMatched','closeFillsMatched','accountFlat','stopFoundInHistory')):
  reasons.append('INDEPENDENT_EXCHANGE_READBACK_INCOMPLETE')
 if audit.get('stopHistoricalStatuses')!=['CANCELED']:
  reasons.append('STOP_TERMINAL_HISTORY_UNVERIFIED')
 if not all(trial.get(k) and trial.get(k)==audit.get(k) for k in
   ('entryOrderId','closeOrderId','stopAlgoId')):
  reasons.append('EXCHANGE_IDENTITIES_DO_NOT_MATCH')
 if trial.get('productionWrites')!=0 or audit.get('productionWrites')!=0:
  reasons.append('PRODUCTION_WRITE_CONTAMINATION')
 mode=live_control.state(ROOT)['mode']
 integrity=live_control.build_errors(ROOT)
 if mode!='STOPPED' or integrity:reasons.append('PRODUCTION_NOT_SAFE_OR_BUILD_INVALID')
 passed=not reasons
 report={'checkedAt':datetime.now(timezone.utc).isoformat(),
  'scope':'WEEX_API_SIM_ONLY','demoProtectedEmergencyCloseCertified':passed,
  'demoReduceOnlyExitCertified':passed,
  'demoStopLifecycleCertified':passed,'demoExchangeReadbackCertified':passed,
  'evidence':{'oneShot':'weex_sim_active_stop_close_trial_20261109.json',
              'independentReadback':'weex_sim_active_stop_close_independent_audit_20261109.json',
              'entryOrderId':trial.get('entryOrderId'),
              'closeOrderId':trial.get('closeOrderId'),
              'attachedStopAlgoId':trial.get('stopAlgoId')},
  'failedChecks':reasons,'productionCrashRecoveryCertified':False,
  'productionEmergencyCloseCertified':False,
  'productionReduceOnlyExitCertified':False,
  'productionNewOrdersAuthorized':False,'pilotExecutionFlagsChanged':False,
  'generalReleaseGateChanged':False,'exchangeWrites':0,
  'mainMode':mode,'buildIntegrityErrors':integrity}
 target=ROOT/'weex_pilot_demo_exit_certification_20261109.json'
 tmp=target.with_suffix('.tmp')
 tmp.write_text(json.dumps(report,indent=2),encoding='utf-8');os.replace(tmp,target)
 return report
if __name__=='__main__':print(json.dumps(certify()))
