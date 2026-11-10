"""Attest supervised-only native stop support in production Lifecycle. No orders."""
import json,hashlib,subprocess,sys,os
from pathlib import Path
from datetime import datetime,timezone
import live_control
R=Path(__file__).resolve().parent
p=R/'live_release_manifest.json'
m=json.loads(p.read_text(encoding='utf-8'))
assert m['status']=='OFFLINE_VERIFIED_NO_REAL_ORDERS'
assert m['testsPassed'] is True
assert set(m['sha256'])==set(live_control.CODE_FILES)
diff=[x for x,h in m['sha256'].items() if hashlib.sha256((R/x).read_bytes()).hexdigest()!=h]
assert diff==['weex_lifecycle.py'],diff
cfg=json.loads((R/'weex_ai_risk_config.json').read_text(encoding='utf-8'))
assert cfg['execution']['enabled'] is False
assert cfg['execution']['mode']=='PRETRADE'
assert live_control.state(R)['mode']=='STOPPED'
modules=['test_weex_supervised_lifecycle_stop_v3',
 'test_weex_supervised_real_reader_v3','test_weex_supervised_real_recovery_v3',
 'test_weex_supervised_crash_executor_v2','test_weex_lifecycle',
 'test_weex_worker_recovery_integration_20261109',
 'test_weex_real_worker_crash_evidence_gate','test_weex_strategy_floor100_20261109']
run=subprocess.run([sys.executable,'-m','unittest','-q',*modules],
 cwd=R,capture_output=True,text=True,timeout=60)
assert run.returncode==0 and 'Ran 98 tests' in run.stderr,run.stderr[-1000:]
source=(R/'weex_lifecycle.py').read_text(encoding='utf-8')
assert "p.get('entrySource')=='supervised_crash_pilot'" in source
assert "p['entry']['slTriggerPrice']=str(stop)" in source
m['sha256']['weex_lifecycle.py']=hashlib.sha256((R/'weex_lifecycle.py').read_bytes()).hexdigest()
m['supervisedCrashAttachedStopV3']={
 'attestedAt':datetime.now(timezone.utc).isoformat(),
 'scope':'ETHUSDT LONG CROSS 100x 0.001 ETH notional max 5 USDT',
 'maxPilotStopOffset':'0.5%','regularStrategyEntryUnchanged':True,
 'testsPassed':98,'exchangeWrites':0,'releaseCertified':False}
m['validationScope']=m.get('validationScope','')+(
 ' One-shot supervised crash pilot only: native exchange MARK_PRICE stop'
 ' preserved in actual production Lifecycle prepared order.'
 ' Strict ETHUSDT 100x/0.001/max $5/stop <=0.5% scope.'
 ' 98 offline tests; no real order, no GO certification.')
tmp=p.with_suffix('.tmp')
tmp.write_text(json.dumps(m,indent=2)+'\n',encoding='utf-8')
os.replace(tmp,p)
assert not live_control.build_errors(R),live_control.build_errors(R)
print(json.dumps({'status':'ATTESTED_NATIVE_PILOT_STOP','tests':98,
 'productionIntegrity':'PASS','botMode':live_control.state(R)['mode'],
 'realOrdersSent':0,'realCrashCertified':False}))
