"""V32 evidence acceptance. Demo evidence may prove demo recovery but never LIVE."""
from pathlib import Path
import json
ROOT=Path(__file__).resolve().parent
def classify(e):
 if not isinstance(e,dict):return {'demoPass':False,'reason':'INVALID_EVIDENCE','liveCrashCertified':False}
 child=e.get('childState') or {}
 criteria={
  'simHostOnly':e.get('host')=='https://api-sim.weex.com' and child.get('host')=='https://api-sim.weex.com',
  'processCrashAfterDispatch':e.get('childExitCode')==73 and child.get('stage')=='ENTRY_OUTCOME_UNKNOWN' and child.get('entryAttemptReserved') is True,
  'exactSingleEntry':e.get('observedEntries')==1 and e.get('exactEntryVerified') is True and e.get('noDuplicateEntry') is True,
  'attachedStopVerified':e.get('activeStops')==1 and e.get('stopVerified') is True,
  'oneShotDemoTransport':e.get('demoEntryPOSTs')==1 and e.get('demoClosePOSTs')==1 and e.get('retries')==0,
  'closeAckAndFlatReadback':e.get('closeAcknowledged') is True and e.get('accountFlat') is True and e.get('remaining')=={'positions':0,'orders':0,'algos':0},
  'productionNotTouched':e.get('realOrders')==0 and child.get('productionWrites')==0,
 }
 return {'status':'SIM_EXCHANGE_POST_ACK_CRASH_AND_CLOSE_VERIFIED' if all(criteria.values()) else 'SIM_EVIDENCE_INCOMPLETE',
         'demoPass':all(criteria.values()),'checks':criteria,
         'liveCrashCertified':False,'readyToRecover':False,'productionReleaseGO':False}
def inspect(root=ROOT):
 p=Path(root)/'weex_demo_crash_recovery_20261109_result.json'
 try:data=json.loads(p.read_text(encoding='utf-8'))
 except (OSError,ValueError):data=None
 return classify(data)
if __name__=='__main__':print(json.dumps(inspect(),ensure_ascii=False))
