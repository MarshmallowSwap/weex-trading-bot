"""Attest targeted Windows Telegram singleton patch without authorizing any trade."""
import hashlib,json,os,subprocess,sys
from pathlib import Path
from datetime import datetime,timezone
import live_control
R=Path(__file__).resolve().parent
mfile=R/'live_release_manifest.json'
m=json.loads(mfile.read_text(encoding='utf-8'))
assert m.get('status')=='OFFLINE_VERIFIED_NO_REAL_ORDERS' and m.get('testsPassed') is True
assert set(m['sha256'])==set(live_control.CODE_FILES)
changed=sorted(f for f,h in m['sha256'].items() if hashlib.sha256((R/f).read_bytes()).hexdigest()!=h)
assert changed==['commands.py'],changed
assert live_control.state(R)['mode']=='STOPPED'
cfg=json.loads((R/'weex_ai_risk_config.json').read_text(encoding='utf-8'))
assert cfg['execution']['enabled'] is False and cfg['execution']['mode']=='PRETRADE'
code=(R/'commands.py').read_text(encoding='utf-8')
assert 'WEEX_Commands_Poller_Singleton' in code and 'Global' in code
test=subprocess.run([sys.executable,'-m','unittest','-q',
  'test_commands_send','test_live_control_release_gate',
  'test_weex_worker_recovery_integration_20261109'],
  cwd=R,capture_output=True,text=True,timeout=60)
assert test.returncode==0,test.stderr[-800:]
assert 'Ran 18 tests' in test.stderr
m['sha256']['commands.py']=hashlib.sha256((R/'commands.py').read_bytes()).hexdigest()
m['telegramSingletonPatch']={'checkedAt':datetime.now(timezone.utc).isoformat(),
  'file':'commands.py','mutex':'Global/WEEX_Commands_Poller_Singleton',
  'regressionTestsPassed':18,'doesNotEnableTrading':True}
m['validationScope']=m.get('validationScope','')+' Commands poller cross-process singleton mutex, 18 scoped regressions passed. No real order or trade activation.'
tmp=mfile.with_suffix('.tmp');tmp.write_text(json.dumps(m,indent=2)+'\n',encoding='utf-8');os.replace(tmp,mfile)
assert not live_control.build_errors(R),live_control.build_errors(R)
print(json.dumps({'status':'ATTESTED','testCount':18,'integrity':'PASS','live':False}))
