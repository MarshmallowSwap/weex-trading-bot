"""Attest reusable no-order Telegram COLLAUDO. No exchange writes or release override."""
import hashlib,json,os,subprocess,sys
from pathlib import Path
from datetime import datetime,timezone
import live_control
R=Path(__file__).resolve().parent
manifest=R/'live_release_manifest.json'
m=json.loads(manifest.read_text(encoding='utf-8'))
assert m['status']=='OFFLINE_VERIFIED_NO_REAL_ORDERS' and m['testsPassed'] is True
assert set(m['sha256'])==set(live_control.CODE_FILES)
changed=sorted(f for f,d in m['sha256'].items() if hashlib.sha256((R/f).read_bytes()).hexdigest()!=d)
assert changed==['commands.py'],changed
assert live_control.state(R)['mode']=='STOPPED'
cfg=json.loads((R/'weex_ai_risk_config.json').read_text(encoding='utf-8'))
assert cfg['execution']['enabled'] is False and cfg['execution']['mode']=='PRETRADE'
commands=(R/'commands.py').read_text(encoding='utf-8')
module=(R/'weex_telegram_collaudo.py').read_text(encoding='utf-8')
assert "command in ('collaudo','/collaudo')" in commands
assert 'fresh_start_message(m)' in commands and 'from_id==allowed_user' in commands
assert 'weex_live_worker.py' not in module
assert "'weex_final_live_status_readonly_20261109.py'" in module
assert "'weex_worker_crash_probe_test_20261109.py'" in module
tests=subprocess.run([sys.executable,'-m','unittest','-q','test_weex_telegram_collaudo',
 'test_commands_send','test_live_control_release_gate','test_weex_worker_recovery_integration_20261109'],
 cwd=R,capture_output=True,text=True,timeout=60)
assert tests.returncode==0 and 'Ran 23 tests' in tests.stderr,tests.stderr[-700:]
m['sha256']['commands.py']=hashlib.sha256((R/'commands.py').read_bytes()).hexdigest()
m['reusableTelegramCollaudo']={'certifiedAt':datetime.now(timezone.utc).isoformat(),
 'commands':['COLLAUDO','/collaudo'],'scope':'READ_ONLY_ACCOUNT_AND_OFFLINE_CRASH',
 'focusedTestsPassed':23,'noRealOrders':True,'cannotAuthorizeProduction':True,
 'realCrashEvidenceRequiredSeparately':True}
m['validationScope']=m.get('validationScope','')+' Reusable COLLAUDO Telegram read-only diagnostic, bounded offline OS crash probe and authenticated GET-only account, 23 tests; no trading start or real crash certification.'
temp=manifest.with_suffix('.tmp');temp.write_text(json.dumps(m,indent=2)+'\n',encoding='utf-8');os.replace(temp,manifest)
assert not live_control.build_errors(R),live_control.build_errors(R)
print(json.dumps({'status':'ATTESTED','integrity':'PASS','tests':23,'tradingEnabled':False,'realCrashCertified':False}))
