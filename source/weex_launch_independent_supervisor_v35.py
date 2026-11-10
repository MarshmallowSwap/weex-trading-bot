"""Launch independent OS supervisor V35 twice to confirm no duplicate recovery/exit."""
import json,os,subprocess,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parent
EXE=getattr(sys,'_base_executable',sys.executable)
SRC=ROOT/'weex_independent_supervisor_replay_v35.py'
EVIDENCE=ROOT/'weex_demo_supervisor_bridge_v34_result.json'
with tempfile.TemporaryDirectory(prefix='weex_independent_supervisor_v35_') as td:
 reports=[]
 for i in range(2):
  cp=subprocess.run([EXE,'-B',str(SRC),td,str(EVIDENCE)],
    capture_output=True,text=True,timeout=30,cwd=str(ROOT))
  try:r=json.loads(cp.stdout.strip())
  except (ValueError,TypeError):r={'status':'PROCESS_OUTPUT_INVALID','exitCode':cp.returncode,'stderrType':'NONZERO' if cp.stderr else 'EMPTY'}
  r['processExitCode']=cp.returncode
  reports.append(r)
 print(json.dumps({'first':reports[0],'second':reports[1],
    'differentSupervisorPids':reports[0].get('supervisorPid')!=reports[1].get('supervisorPid'),
    'sameProductionWorkerFileUsed':(reports[0].get('workerCodeHash')==reports[1].get('workerCodeHash'))},ensure_ascii=False))
