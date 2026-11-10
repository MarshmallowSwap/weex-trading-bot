"""Restore manifest after reverting an unnecessary Telegram singleton experiment."""
import hashlib,json,os,subprocess,sys
from pathlib import Path
from datetime import datetime,timezone
import live_control
R=Path(__file__).resolve().parent
mfile=R/'live_release_manifest.json'
m=json.loads(mfile.read_text(encoding='utf-8'))
assert m['status']=='OFFLINE_VERIFIED_NO_REAL_ORDERS' and m['testsPassed'] is True
assert set(m['sha256'])==set(live_control.CODE_FILES)
modified=[f for f,h in m['sha256'].items() if hashlib.sha256((R/f).read_bytes()).hexdigest()!=h]
assert modified==['commands.py'],modified
source=(R/'commands.py').read_text(encoding='utf-8')
assert 'WEEX_Commands_Poller_Singleton' not in source
assert 'telegram_commands.singleton.lock' not in source
assert 'def main():\n    conn=sqlite3.connect(DB)' in source
assert live_control.state(R)['mode']=='STOPPED'
cfg=json.loads((R/'weex_ai_risk_config.json').read_text(encoding='utf-8'))
assert cfg['execution']['enabled'] is False and cfg['execution']['mode']=='PRETRADE'
tests=subprocess.run([sys.executable,'-m','unittest','-q',
 'test_commands_send','test_live_control_release_gate','test_weex_worker_recovery_integration_20261109'],
 cwd=R,text=True,capture_output=True,timeout=60)
assert tests.returncode==0 and 'Ran 18 tests' in tests.stderr,tests.stderr[-900:]
m['sha256']['commands.py']=hashlib.sha256((R/'commands.py').read_bytes()).hexdigest()
m['telegramSingletonPatch']={'status':'REVERTED_AFTER_IDENTIFYING_NORMAL_VENV_PARENT_CHILD',
 'at':datetime.now(timezone.utc).isoformat(),'regressionTests':18}
m['validationScope']=m.get('validationScope','')+' Telegram singleton experiment reverted: pythonw venv launcher and base Python process are parent-child, not duplicate pollers. 18 regression tests after restore.'
tmp=mfile.with_suffix('.tmp');tmp.write_text(json.dumps(m,indent=2)+'\n',encoding='utf-8');os.replace(tmp,mfile)
assert not live_control.build_errors(R),live_control.build_errors(R)
print(json.dumps({'status':'RESTORED','integrity':'PASS','tests':18,'tradingMode':'STOPPED'}))
