"""Rerun offline regressions and re-attest changed worker build without GO."""
import hashlib,json,os,re,subprocess,sys
from pathlib import Path
from datetime import datetime,timezone
import live_control
ROOT=Path(__file__).resolve().parent
TESTS="""test_weex_lifecycle test_live_control_release_gate
test_weex_supervised_lifecycle_stop_v3 test_weex_supervised_gateway_scope_v5
test_weex_supervised_recovery_orchestrator_v6 test_weex_independent_incident_supervisor_v6
test_weex_v5_entry_fail_closed_20261109 test_weex_supervised_v5_safety_audit_20261109
test_weex_supervised_entry_permit_v5 test_weex_supervised_crash_watchdog_v4
test_weex_supervised_reduceonly_close_transport_v4 test_weex_supervised_one_shot_permission_v4
test_weex_supervised_reduce_only_close_plan_v4 test_weex_supervised_exit_policy_v7
test_weex_supervised_process_monitor_v6 test_weex_supervised_worker_recovery_process_v8
test_weex_supervised_exact_close_readback_v6 test_weex_supervised_entry_authority_bridge_v8""".split()
def main():
 if live_control.state(ROOT)['mode']!='STOPPED':raise PermissionError('BOT_NOT_STOPPED')
 gate=ROOT/'live_release_gate_latest.json'
 old_gate=gate.read_bytes() if gate.exists() else None
 files=live_control.CODE_FILES
 if len(files)!=len(set(files)):raise ValueError('DUPLICATE_FILES')
 hashes={f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in files}
 cli=subprocess.run([sys.executable,'-B',str(ROOT/'weex_live_worker.py'),'--supervised-crash-child'],
   cwd=str(ROOT),capture_output=True,text=True,timeout=15)
 if cli.returncode!=3 or 'INDEPENDENT_SUPERVISOR_NOT_READY' not in cli.stdout:
  raise PermissionError('SUPERVISED_WORKER_NOT_FAIL_CLOSED')
 test=subprocess.run([sys.executable,'-m','unittest','-q',*TESTS],cwd=str(ROOT),
  capture_output=True,text=True,timeout=180)
 output=test.stdout+'\n'+test.stderr
 matched=re.search(r'Ran (\d+) tests? in ',output)
 if test.returncode!=0 or not matched or '\nOK' not in output:
  print(output[-2500:]);raise RuntimeError('OFFLINE_TEST_FAILURE')
 count=int(matched.group(1))
 if count<120:raise RuntimeError('INSUFFICIENT_TEST_COUNT')
 if live_control.state(ROOT)['mode']!='STOPPED':raise PermissionError('STATE_CHANGED')
 if any(hashlib.sha256((ROOT/f).read_bytes()).hexdigest()!=digest for f,digest in hashes.items()):
  raise PermissionError('CODE_CHANGED_DURING_TEST')
 if gate.exists() and gate.read_bytes()!=old_gate:raise PermissionError('GATE_CHANGED')
 manifest=ROOT/'live_release_manifest.json'
 previous=json.loads(manifest.read_text(encoding='utf-8'))
 backup=ROOT/'live_release_manifest.before_supervised_worker_20261109.json'
 if not backup.exists():backup.write_text(json.dumps(previous,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
 updated={**previous,'status':'OFFLINE_VERIFIED_NO_REAL_ORDERS','testsPassed':True,
  'testCount':count,'sha256':hashes,'releasedAt':datetime.now(timezone.utc).isoformat(),
  'validationScope':f'{count} explicitly named offline unittest cases, supervised worker CLI fail-closed; no live exchange POST; independent live release gate unchanged.',
  'liveGoCertified':False,'remainingLiveBlockers':['crash_restart_recovery_live_tested'],
  'realOrdersSentDuringValidation':False}
 tmp=manifest.with_suffix('.supervised.tmp')
 tmp.write_text(json.dumps(updated,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
 os.replace(tmp,manifest)
 if live_control.build_errors(ROOT):raise RuntimeError('POST_ATTEST_HASH_MISMATCH')
 print(json.dumps({'status':'OFFLINE_BUILD_REATTESTED','testCount':count,
  'hashedFiles':len(hashes),'supervisedCliNoDispatch':True,'releaseGateChanged':False,
  'liveGoCertified':False,'liveMode':live_control.state(ROOT)['mode']}))
if __name__=='__main__':main()
