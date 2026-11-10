"""Bounded GET-only reconciliation refresh; protect WEEX emergency API headroom.

Never grants LIVE, never sends orders, never edits positions. All steps are
one-off independent programs; release report generated only after proofs.
"""
from pathlib import Path
import json,subprocess,sys,time
from weex_api_budget import Budget
ROOT=Path(__file__).resolve().parent
STEPS=[
 ('trade_history','live_pilot_paginated_reconciliation.py'),
 ('fill_order_binding','reconcile_recent_fills_readonly.py'),
 ('account_protection','position_manager_integrated.py'),
 ('operational_reconciliation','account_reconciliation_point1.py'),
 ('release_gate','live_release_gate.py')]
MIN_AVAILABLE=330 # 150 reserved emergency + ~180 max planned diagnostics
def remaining():
 b=Budget(ROOT)
 with b.db() as c:
  now=time.time()
  used=c.execute('SELECT COALESCE(SUM(weight),0) FROM api_calls_v1 WHERE at>?',(now-600,)).fetchone()[0]
 return 490-int(used)
result={'status':'DEFERRED','mode':'READ_ONLY','exchangeWrites':0,
        'minRequiredAvailable':MIN_AVAILABLE,'steps':[]}
for _ in range(9):
 avail=remaining()
 print('API_HEADROOM',avail,flush=True)
 if avail>=MIN_AVAILABLE:break
 time.sleep(10)
else:
 result['reason']='BUDGET_HEADROOM_BELOW_SAFE_RESERVE'
 print(json.dumps(result),flush=True)
 raise SystemExit(0)
for label,file in STEPS:
 try:
  reserve=Budget(ROOT).require_supervised_recovery_headroom(preflight_weight=0)
  if reserve is not True:
   result['reason']='RECOVERY_API_RESERVE_FAILED';break
 except Exception as exc:
  result['reason']='RECOVERY_API_RESERVE_'+type(exc).__name__;break
 before=remaining()
 command=[sys.executable,'-B',str(ROOT/file)]
 try:
  p=subprocess.run(command,cwd=str(ROOT),capture_output=True,text=True,timeout=40)
  stdout=p.stdout[-1800:]
  step={'name':label,'exitCode':p.returncode,'availableBefore':before,
         'availableAfter':remaining(),'outputTail':stdout,
         'errorType':None if p.returncode==0 else 'STEP_NONZERO'}
  result['steps'].append(step)
  print('STEP',json.dumps(step,ensure_ascii=False),flush=True)
  if p.returncode!=0:
   result['reason']='STEP_FAILED_'+label;break
 except (OSError,subprocess.TimeoutExpired) as exc:
  result['reason']='STEP_EXCEPTION_'+type(exc).__name__;break
else:result['status']='REFRESH_COMPLETED'
result['availableAtEnd']=remaining()
print('FINAL',json.dumps(result,ensure_ascii=False),flush=True)
