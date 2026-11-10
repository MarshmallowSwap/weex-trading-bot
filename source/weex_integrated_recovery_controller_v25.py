"""WEEX independent recovery integration controller: repeatable safe drill.

Runs true worker recovery CLI in a child and the exact exit call chain with
faked exchange evidence in isolated SQLite. Reads production task and cross
conditions but NEVER grants or uses a production one-shot permit, nor sends
an exchange request, nor changes the live gate.
"""
from __future__ import annotations
import json,subprocess,sys,time
from pathlib import Path
from datetime import datetime,timezone
from weex_operational_recovery_controller_v24 import check as inspect_prearm

ROOT=Path(__file__).resolve().parent
TESTS=('test_weex_real_worker_recovery_subprocess_v25',
       'test_weex_supervisor_exit_callchain_v25',
       'test_weex_operational_recovery_controller_v24',
       'test_weex_supervisor_exit_cross_integration_v23')

def run(root=ROOT,*,runner=None,prearm_reader=None):
 root=Path(root)
 base={'checkedAt':datetime.now(timezone.utc).isoformat(),
       'status':'CONTROLLER_INTEGRATED_DRILL_INCOMPLETE',
       'networkWrites':0,'productionWrites':0,'permitsGranted':0,
       'liveModeChanged':False,'readyToRecover':False,
       'heartbeatPromotionAllowed':False,'liveCrashCertified':False,
       'entryAllowed':False,'closeAllowed':False,
       'testModules':list(TESTS)}
 try:
  reader=prearm_reader or inspect_prearm
  prearm=reader(root)
  base['prearm']={k:prearm.get(k) for k in
       ('status','blockers','taskVerified','monitorLive',
        'accountFlatForNewCrossEntry','exitPermissionGranted','apiHeadroomReady')}
 except Exception as exc:
  base['prearm']={'status':'PREARM_READ_FAILED','errorType':type(exc).__name__}
 try:
  command=[sys.executable,'-m','unittest','-q',*TESTS]
  call=runner or (lambda:subprocess.run(command,cwd=str(ROOT),
                 stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=40))
  out=call()
  passed=out.returncode==0 and 'OK' in out.stderr and 'FAILED' not in out.stderr
  base['drillTestsPassed']=passed
  base['testExitCode']=out.returncode
  base['testSummary']=out.stderr.strip()[-500:]
  if passed:
   base['status']='ISOLATED_REAL_WORKER_AND_EXIT_CHAIN_DRILL_PASS_NO_LIVE_CERTIFICATION'
 except Exception as exc:
  base['status']='DRILL_EXECUTION_UNCERTAIN'
  base['drillErrorType']=type(exc).__name__
 # Real promotion requires an independently observed protected post-ACK
 # incident, live authorized close, exact readback and CROSS admission.
 # Neither fake evidence nor a local unit test can satisfy this gate.
 return base

if __name__=='__main__':
 print(json.dumps(run(),ensure_ascii=False))
