"""Independent production worker certification readiness (GET-only, no release mutation).

Never fabricates attestations. Distinguishes code/integrity, live recovery
readiness and independent real crash evidence.
"""
import json,hashlib,time
from datetime import datetime,timezone
from pathlib import Path
import live_control
from weex_real_worker_crash_evidence_gate import certify
from weex_supervised_exit_policy_v7 import status as exit_status
from weex_supervised_crash_entry_child_v5 import supervisor_ready,process_alive
from weex_supervised_entry_authority_bridge_v8 import ready
ROOT=Path(__file__).resolve().parent
def inspect(root=ROOT):
 root=Path(root)
 s=live_control.state(root)
 errors=live_control.build_errors(root)
 approved=exit_status(root)
 gate=ready(root)
 proof=certify(root)
 monitor={}
 try:monitor=json.loads((root/'weex_supervised_crash_supervisor_health.json').read_text(encoding='utf-8'))
 except (OSError,ValueError,TypeError):pass
 heartbeat=bool(monitor and isinstance(monitor.get('pid'),int) and process_alive(monitor['pid'])
                and 0<=time.time()-float(monitor.get('heartbeatEpoch',0))<=9)
 findings=[]
 if s.get('mode')!='STOPPED':findings.append('PRODUCTION_STRATEGY_NOT_STOPPED')
 if errors:findings.append('PRODUCTION_INTEGRITY_ERRORS')
 if not heartbeat:findings.append('INDEPENDENT_MONITOR_HEARTBEAT_MISSING')
 if not supervisor_ready(root):findings.append('INDEPENDENT_CLOSE_AND_RESTART_NOT_ARMED')
 if approved.get('canClose') is not True:findings.append('EXACT_EXIT_AUTHORIZATION_MISSING')
 if not gate['ready']:findings.append('ENTRY_BRIDGE_'+gate['reason'])
 if proof.get('certified') is not True:findings.append('REAL_CRASH_PROOF_'+proof.get('reason','UNKNOWN'))
 report={'checkedAt':datetime.now(timezone.utc).isoformat(),
         'status':'CERTIFIED_REAL_WORKER' if proof.get('certified') is True and not findings else 'PRODUCTION_CERTIFICATION_NOT_YET_POSSIBLE',
         'source':'READ_ONLY_INDEPENDENT_ATTESTATION',
         'workerSha256':hashlib.sha256((root/'weex_live_worker.py').read_bytes()).hexdigest(),
         'workerCodeIntegrityPass':not bool(errors),
         'liveMode':s.get('mode'),'supervisorHeartbeatLive':heartbeat,
         'supervisorRecoveryArmed':supervisor_ready(root),
         'exactExitAuthorized':approved.get('canClose') is True,
         'entryBridgeReady':gate.get('ready') is True,
         'realCrashCertified':proof.get('certified') is True,
         'realCrashReason':proof.get('reason'),
         'blockers':findings,'exchangeWrites':0,
         'productionGateModified':False}
 return report
if __name__=='__main__':
 report=inspect()
 target=ROOT/'weex_production_worker_certification_readiness_20261110.json'
 temporary=target.with_suffix('.tmp')
 temporary.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n',encoding='utf-8')
 temporary.replace(target)
 print(json.dumps(report,ensure_ascii=False))
