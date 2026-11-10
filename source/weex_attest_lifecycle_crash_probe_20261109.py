"""Attest exact tested lifecycle change without changing production release gates."""
import hashlib,json,os,subprocess,sys
from pathlib import Path
from datetime import datetime,timezone
import live_control
R=Path(__file__).resolve().parent
manifest=R/'live_release_manifest.json'
m=json.loads(manifest.read_text(encoding='utf-8'))
assert m['status']=='OFFLINE_VERIFIED_NO_REAL_ORDERS' and m['testsPassed'] is True
assert set(m['sha256'])==set(live_control.CODE_FILES)
changed=sorted(n for n,v in m['sha256'].items() if hashlib.sha256((R/n).read_bytes()).hexdigest()!=v)
assert changed==['weex_lifecycle.py'],changed
assert live_control.state(R)['mode']=='STOPPED'
cfg=json.loads((R/'weex_ai_risk_config.json').read_text(encoding='utf-8'))
assert cfg['execution']['enabled'] is False and cfg['execution']['mode']=='PRETRADE'
probe=subprocess.run([sys.executable,'-B','weex_worker_crash_probe_test_20261109.py'],
                     cwd=R,capture_output=True,text=True,timeout=30)
assert probe.returncode==0,probe.stderr[-500:]
out=json.loads(probe.stdout.strip())
assert out['status']=='PASS' and out['childExitCode']==79
assert out['duplicateEntries']==0 and out['recoveredState']=='PROTECTED'
assert out['liveOrders']==0 and out['networkRequests']==0
assert out['productionGatewayHasCrashHook'] is False
tests=subprocess.run([sys.executable,'-m','unittest','-q',
  'test_weex_lifecycle','test_weex_full_lifecycle_os_crash_drill',
  'test_weex_worker_recovery_integration_20261109',
  'test_weex_worker_recovery_readonly_20261109'],cwd=R,capture_output=True,text=True,timeout=60)
assert tests.returncode==0,tests.stderr[-1000:]
assert 'Ran 56 tests' in tests.stderr,tests.stderr[-500:]
m['sha256']['weex_lifecycle.py']=hashlib.sha256((R/'weex_lifecycle.py').read_bytes()).hexdigest()
m['lifecycleCrashProbeIntegration']={'at':datetime.now(timezone.utc).isoformat(),
 'file':'weex_lifecycle.py','focusedRegressionTests':56,'osCrashExitCode':79,
 'noDuplicateEntry':True,'recoveredProtection':True,'simulatedExchangeOnly':True,
 'actualRealExchangeCrashCertified':False,'newRealOrders':0}
m['validationScope']=m.get('validationScope','')+' Lifecycle test-only injection seam after ENTRY ACK before SQLite receipt; 56 regression tests + real OS exit 79 on isolated durable fake exchange. No real crash certification or LIVE authorization.'
tmp=manifest.with_suffix('.tmp');tmp.write_text(json.dumps(m,indent=2)+'\n',encoding='utf-8');os.replace(tmp,manifest)
assert live_control.build_errors(R)==[],live_control.build_errors(R)
print(json.dumps({'status':'ATTESTED','changedFile':'weex_lifecycle.py',
  'regressionTests':56,'integrity':'PASS','realTradingEnabled':False,
  'realCrashCertified':False}))
