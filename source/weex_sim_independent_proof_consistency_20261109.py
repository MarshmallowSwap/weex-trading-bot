"""Independent offline consistency audit of recorded WEEX API-SIM proof.
Never claims live certification; never reads credentials or writes to the exchange.
"""
from pathlib import Path
from datetime import datetime,timezone
import json
ROOT=Path(__file__).resolve().parent
TRIAL='weex_sim_active_stop_close_trial_20261109_run2.json'
AUDIT='weex_sim_active_stop_close_independent_audit_20261109_run2.json'
def verify(root=ROOT):
 root=Path(root)
 try:
  trial=json.loads((root/TRIAL).read_text(encoding='utf-8'))
  proof=json.loads((root/AUDIT).read_text(encoding='utf-8'))
 except (OSError,ValueError) as exc:
  return {'status':'BLOCKED','reason':'EVIDENCE_UNAVAILABLE_OR_INVALID','errorType':type(exc).__name__,'realCertified':False}
 checks={
  'simulationHost':trial.get('host')==proof.get('host')=='https://api-sim.weex.com',
  'trialCompleted':trial.get('stage')=='SIM_ACTIVE_STOP_CLOSE_VERIFIED',
  'singleEntry':trial.get('entryAttemptReserved') is True and trial.get('simEntryPosts')==1,
  'singleClose':trial.get('closeAttemptReserved') is True and trial.get('simClosePosts')==1,
  'stopProtected':trial.get('stopVerifiedBeforeClose') is True and proof.get('stopFoundInHistory') is True,
  'stopTerminated':proof.get('stopHistoricalStatuses')==['CANCELED'] and trial.get('remainingStopAlgoIds')==[],
  'reduceOnly':trial.get('reduceOnlyCloseVerified') is True and proof.get('closeFillsMatched') is True,
  'flat':trial.get('positionFlatVerified') is True and proof.get('accountFlat') is True and all(
    trial.get(k)==0 for k in ('postClosePositions','postCloseRegularOrders','postCloseConditionalAlgos')),
  'independentReadback':proof.get('independentProofPass') is True and all(
    proof.get(k) is True for k in ('entryMatched','closeMatched')),
  'matchingIDs':all(str(trial.get(k))==str(proof.get(k)) and str(trial.get(k,'')).isdigit()
    for k in ('entryOrderId','closeOrderId','stopAlgoId')),
  'zeroProductionWrites':trial.get('productionWrites')==proof.get('productionWrites')==0,
  'readOnlyAudit':proof.get('demoWrites')==0,
 }
 return {'checkedAt':datetime.now(timezone.utc).isoformat(),
  'status':'SIM_RECORDED_EVIDENCE_CONSISTENT' if all(checks.values()) else 'SIM_EVIDENCE_INCOMPLETE',
  'checks':checks,'passed':sum(checks.values()),'total':len(checks),
  'liveWorkerCrashObserved':False,'realCertified':False,'productionWrites':0,
  'note':'Consistent saved files are not a fresh authenticated exchange readback.'}
if __name__=='__main__':print(json.dumps(verify(),indent=2))
