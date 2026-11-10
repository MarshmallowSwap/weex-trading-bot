"""Attest bounded public scanner API use without enabling real trading."""
import hashlib,json,os,subprocess,sys
from pathlib import Path
from datetime import datetime,timezone
import live_control
R=Path(__file__).resolve().parent
mf=R/'live_release_manifest.json'
m=json.loads(mf.read_text(encoding='utf-8'))
assert m.get('status')=='OFFLINE_VERIFIED_NO_REAL_ORDERS'
assert m.get('testsPassed') is True
assert set(m['sha256'])==set(live_control.CODE_FILES)
changed=sorted(f for f,h in m['sha256'].items()
 if hashlib.sha256((R/f).read_bytes()).hexdigest()!=h)
assert changed==['weex_scan_data.py'],changed
assert live_control.state(R)['mode']=='STOPPED'
risk=json.loads((R/'weex_ai_risk_config.json').read_text(encoding='utf-8'))
assert risk['execution']['enabled'] is False and risk['execution']['mode']=='PRETRADE'
from weex_scan_data import MAX_PUBLIC_SCANNER_REQUESTS_PER_CYCLE,MAX_SHARED_API_WEIGHT_BEFORE_SCANNER_PAUSE
assert MAX_PUBLIC_SCANNER_REQUESTS_PER_CYCLE==220
assert MAX_SHARED_API_WEIGHT_BEFORE_SCANNER_PAUSE==300
names=['test_weex_scan_recovery_headroom_20261109','test_weex_api_budget_dynamic',
 'test_weex_worker_recovery_integration_20261109','test_live_control_release_gate',
 'test_weex_lifecycle','test_live_release_gate']
t=subprocess.run([sys.executable,'-m','unittest','-q',*names],
 cwd=R,capture_output=True,text=True,timeout=60)
assert t.returncode==0 and 'Ran 65 tests' in t.stderr,t.stderr[-1000:]
m['sha256']['weex_scan_data.py']=hashlib.sha256((R/'weex_scan_data.py').read_bytes()).hexdigest()
m['scannerRecoveryApiHeadroom']={'at':datetime.now(timezone.utc).isoformat(),
  'maxRequestsPerScanner':220,'sharedRequestWeightPause':300,
  'exchangeDeclaredTenMinuteWeightCeiling':490,
  'testsPassed':65,'exchangeWrites':0,'tradingEnabled':False,
  'scannerResultsArePartialWhenQuotaReached':True}
m['validationScope']=m.get('validationScope','')+(
 ' Public-data scanner capped at 220 network requests/instance and paused at'
 ' shared ten-minute weight 300; account/recovery GETs retain headroom.'
 ' Incomplete symbols remain unavailable rather than fabricated.'
 ' 65 targeted offline tests; no orders or production release authorization.')
tmp=mf.with_suffix('.tmp')
tmp.write_text(json.dumps(m,indent=2)+'\n',encoding='utf-8')
os.replace(tmp,mf)
assert not live_control.build_errors(R),live_control.build_errors(R)
print(json.dumps({'status':'ATTESTED','integrity':'PASS','tests':65,
 'trading':live_control.state(R)['mode'],'realCrashCertified':False}))
