"""WEEX staged supervisor promotion policy; read-only, fail-closed.

Evaluates the exact production ETH crash trial. Never writes the heartbeat,
issues a permit, starts a worker, or dispatches orders. A valid assessment
is *not* READY_TO_RECOVER. The actual S4U monitor must separately implement
and prove every safety capability before a live state can be published.
"""
from __future__ import annotations
import json,time
from pathlib import Path
from weex_independent_recovery_capability_v14 import check as capability_check
from weex_account_observation import load
ROOT=Path(__file__).resolve().parent

def assess(capabilities, snapshot, *, now=None, max_account_age=8):
 at=time.time() if now is None else float(now)
 blockers=[]
 c=capabilities if isinstance(capabilities,dict) else {}
 for name,reason in (
  ('taskS4UVerified','S4U_TASK_NOT_CONFIRMED'),
  ('supervisorHeartbeatLive','HEARTBEAT_NOT_LIVE'),
  ('productionIntegrityPass','CODE_INTEGRITY_NOT_VALID'),
  ('reduceOnlySdkPreviewPass','REDUCE_ONLY_CLOSE_SERIALIZATION_MISSING'),
  ('apiHeadroomReady','API_HEADROOM_NOT_SUFFICIENT')):
  if c.get(name) is not True:blockers.append(reason)
 # An exact future exit permit must be operator-approved outside the monitor.
 if c.get('exitPermitActive') is not True:blockers.append('EXACT_EXIT_ONE_SHOT_PERMIT_ABSENT')
 # NEVER require UNKNOWN pre-entry; it can exist only AFTER the intentionally
 # crashed worker has submitted the test order. It is a POST-CRASH gate.
 if snapshot is None or not isinstance(snapshot,dict) or snapshot.get('complete') is not True:
  blockers.append('FRESH_CROSS_ACCOUNT_SNAPSHOT_REQUIRED')
 else:
  try:
   started=float(snapshot['startedAtMs'])/1000
   completed=float(snapshot['completedAtMs'])/1000
   fresh=0<=at-started<=max_account_age and 0<=completed-started<=5
  except (KeyError,TypeError,ValueError):fresh=False
  if not fresh:blockers.append('ACCOUNT_SNAPSHOT_EXPIRED')
  fields=('positions','regularOrders','conditionalOrders','trailingOrders')
  groups=[snapshot.get(k) for k in fields]
  if any(not isinstance(v,list) for v in groups):
   blockers.append('ACCOUNT_SNAPSHOT_INCOMPLETE')
  elif any(groups):
   # Unlike EXIT readback, ENTRY risk is account-wide under CROSS.
   blockers.append('SHARED_CROSS_COLLATERAL_NOT_FLAT')
 # READY state requires more than a sound monitor and SDK preview.
 # It must be promoted by an independently tested S4U controller that can
 # actually honor its advertised close/restart capabilities. None is yet
 # installed; do not trust external booleans in capabilities to assert it.
 blockers.append('VERIFIED_OPERATIONAL_PROMOTION_CONTROLLER_NOT_INSTALLED')
 return {'state':'PROMOTION_BLOCKED' if blockers else 'CANDIDATE_VALIDATED',
  'blockers':blockers,'apiHeadroomReady':c.get('apiHeadroomReady') is True,
  'crossAccountFlat': 'SHARED_CROSS_COLLATERAL_NOT_FLAT' not in blockers and
                      'FRESH_CROSS_ACCOUNT_SNAPSHOT_REQUIRED' not in blockers and
                      'ACCOUNT_SNAPSHOT_EXPIRED' not in blockers and
                      'ACCOUNT_SNAPSHOT_INCOMPLETE' not in blockers,
  'realWorkerUnknownRequiredBeforeEntry':False,
  'realWorkerUnknownRequiredAfterCrash':True,
  'heartbeatPromotionAllowed':False,'entryAuthorized':False,
  'closeAuthorized':False,'productionReleaseCertified':False,
  'exchangeWrites':0}

def inspect(root=ROOT):
 root=Path(root)
 caps=capability_check(root)
 snapshot=load(root,max_age=8)
 result=assess(caps,snapshot)
 result['source']='INDEPENDENT_READONLY_PREARM_AUDIT'
 return result

if __name__=='__main__':
 result=inspect()
 print(json.dumps(result,ensure_ascii=False))
