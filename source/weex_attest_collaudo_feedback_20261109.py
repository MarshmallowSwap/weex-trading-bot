"""Attest COLLAUDO display-only revision. No exchange orders or start."""
import hashlib,json,os,subprocess,sys
from pathlib import Path
from datetime import datetime,timezone
import live_control
R=Path(__file__).resolve().parent
manifest=R/'live_release_manifest.json'
m=json.loads(manifest.read_text(encoding='utf-8'))
assert m['status']=='OFFLINE_VERIFIED_NO_REAL_ORDERS' and m['testsPassed'] is True
assert set(m['sha256'])==set(live_control.CODE_FILES)
modified=sorted(f for f,h in m['sha256'].items()
 if hashlib.sha256((R/f).read_bytes()).hexdigest()!=h)
assert modified==['weex_telegram_collaudo.py'],modified
assert live_control.state(R)['mode']=='STOPPED'
cfg=json.loads((R/'weex_ai_risk_config.json').read_text(encoding='utf-8'))
assert cfg['execution']['enabled'] is False and cfg['execution']['mode']=='PRETRADE'
result=subprocess.run([sys.executable,'-m','unittest','-q',
 'test_weex_telegram_collaudo','test_weex_real_worker_crash_evidence_gate',
 'test_live_release_gate','test_live_control_release_gate'],
 cwd=R,text=True,capture_output=True,timeout=40)
assert result.returncode==0 and 'Ran 34 tests' in result.stderr,result.stderr[-700:]
m['sha256']['weex_telegram_collaudo.py']=hashlib.sha256(
 (R/'weex_telegram_collaudo.py').read_bytes()).hexdigest()
m['collaudoLatestFeedback']={'at':datetime.now(timezone.utc).isoformat(),
  'tests':34,'showsFreshReadOnlyRefresh':True,
  'showsIndependentRealCrashProofFailure':True,'noNewOrders':True}
tmp=manifest.with_suffix('.tmp')
tmp.write_text(json.dumps(m,indent=2)+'\n',encoding='utf-8')
os.replace(tmp,manifest)
assert live_control.build_errors(R)==[],live_control.build_errors(R)
print(json.dumps({'status':'ATTESTED','tests':34,'integrity':'PASS',
 'trading':live_control.state(R)['mode']}))
