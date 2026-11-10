"""Fail-closed independent V5 safety audit. No credentials, network writes or release changes."""
import ast,json,hashlib
from pathlib import Path
from datetime import datetime,timezone

ROOT=Path(__file__).resolve().parent
FILES={
 'entry':'weex_supervised_crash_entry_child_v5.py',
 'permit':'weex_supervised_entry_permit_v5.py',
 'watchdog':'weex_supervised_crash_watchdog_v4.py',
 'recovery':'weex_supervised_recovery_watchdog_v5.py',
 'close':'weex_supervised_reduceonly_close_transport_v4.py',
}
def audit(root=ROOT):
 root=Path(root)
 missing=[p for p in FILES.values() if not (root/p).is_file()]
 if missing:return {'status':'BLOCKED','missing':missing,'releaseEligible':False}
 source=(root/FILES['entry']).read_text(encoding='utf-8')
 tree=ast.parse(source)
 hardcoded=[]
 for node in ast.walk(tree):
  if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id=='authorize_once':
   for kw in node.keywords:
    if kw.arg=='approval' and isinstance(kw.value,ast.Constant) and kw.value.value is True:
     hardcoded.append('HARDCODED_EXTERNAL_APPROVAL_TRUE')
  if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='context' for t in node.targets):
   if isinstance(node.value,ast.Dict):
    for k,v in zip(node.value.keys,node.value.values):
     if isinstance(k,ast.Constant) and k.value in ('atomicStopVerified','closePathValidated','productionIntegrity','accountFlat','independentSupervisorReady','apiBudgetReady') and isinstance(v,ast.Constant) and v.value is True:
      hardcoded.append('UNPROVEN_CONTEXT_'+k.value)
 supervisor=(root/FILES['watchdog']).read_text(encoding='utf-8')
 recovery=(root/FILES['recovery']).read_text(encoding='utf-8')
 close=(root/FILES['close']).read_text(encoding='utf-8')
 blockers=sorted(set(hardcoded))
 if 'authorizedToClose\x27:False' in supervisor or '"authorizedToClose":False' in supervisor:
  blockers.append('READONLY_WATCHDOG_CANNOT_CLOSE')
 if 'simulated exchange only' in recovery.lower():
  blockers.append('DOUBLE_CRASH_RECOVERY_SIMULATION_ONLY')
 if 'external exact-operation approval' in close.lower():
  blockers.append('CLOSE_REQUIRES_SEPARATE_EXTERNAL_APPROVAL')
 worker_path=root/'weex_live_worker.py'
 if not worker_path.is_file():
  blockers.append('PRODUCTION_WORKER_MISSING')
 else:
  worker_source=worker_path.read_text(encoding='utf-8')
  bridge_path=root/'weex_supervised_entry_authority_bridge_v8.py'
  direct=('weex_supervised_crash_entry_child_v5' in worker_source)
  bridged=(bridge_path.is_file() and
           'weex_supervised_entry_authority_bridge_v8' in worker_source and
           'run_connected(ROOT)' in worker_source and
           'from weex_supervised_crash_entry_child_v5 import run_child' in bridge_path.read_text(encoding='utf-8') and
           'return run_child(root,' in bridge_path.read_text(encoding='utf-8'))
  if '--supervised-crash-child' not in worker_source or not (direct or bridged):
   blockers.append('V5_ENTRY_NOT_WIRED_IN_PRODUCTION_WORKER')
 if not (root/'weex_real_worker_crash_attestation.json').is_file():
  blockers.append('REAL_CRASH_ATTESTATION_MISSING')
 report={'checkedAt':datetime.now(timezone.utc).isoformat(),'status':'BLOCKED' if blockers else 'REVIEW_REQUIRED',
  'releaseEligible':False,'blockingFindings':blockers,
  'fileSha256':{key:hashlib.sha256((root/name).read_bytes()).hexdigest() for key,name in FILES.items()},
  'ordersSent':0,'productionGateModified':False}
 return report
if __name__=='__main__':print(json.dumps(audit(),indent=2))
