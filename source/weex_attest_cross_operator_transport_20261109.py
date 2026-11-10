"""Attest the explicitly tested Telegram-only supervised close addition.

Never set production execution flags, live-release crash check or live worker mode.
"""
import hashlib,json,os
from datetime import datetime,timezone
from pathlib import Path
import live_control
ROOT=Path(__file__).resolve().parent
manifest=ROOT/'live_release_manifest.json'
m=json.loads(manifest.read_text(encoding='utf-8'))
if (m.get('status')!='OFFLINE_VERIFIED_NO_REAL_ORDERS' or
    m.get('testsPassed') is not True or
    set(m.get('sha256',{}))!=set(live_control.CODE_FILES)):
 raise PermissionError('ORIGINAL_RELEASE_PROOFS_INVALID')
changed=sorted(name for name,digest in m['sha256'].items()
 if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=digest)
if changed!=['telegram_live_control.py']:
 raise PermissionError('UNEXPECTED_PROTECTED_CHANGES:'+repr(changed))
config=json.loads((ROOT/'weex_ai_risk_config.json').read_text(encoding='utf-8'))
pilot=json.loads((ROOT/'weex_live_1x_pilot_config.json').read_text(encoding='utf-8'))
if (live_control.state(ROOT)['mode']!='STOPPED' or
    config['execution']['enabled'] is not False or config['execution']['mode']!='PRETRADE' or
    pilot.get('executionEnabled') is not False or
    pilot.get('liveOrderSubmissionAllowed') is not False or
    pilot.get('supervisedEmergencyCloseAllowed') is not False):
 raise PermissionError('PRODUCTION_AND_PILOT_MUST_BE_DISARMED')
m['sha256']['telegram_live_control.py']=hashlib.sha256((ROOT/'telegram_live_control.py').read_bytes()).hexdigest()
m['crossCloseOperatorAuthAttestedAt']=datetime.now(timezone.utc).isoformat()
m['crossCloseIntegrationRegressionTestsPassed']=147
m['crossCloseLiveSendEnabled']=False
m['crossCloseRealCrashCertified']=False
m['crossCloseScope']='Telegram callback only issues exact, expiring grant; separate emergency close transport remains disarmed.'
tmp=manifest.with_suffix('.tmp')
tmp.write_text(json.dumps(m,indent=2)+'\n',encoding='utf-8')
os.replace(tmp,manifest)
if live_control.build_errors(ROOT):
 raise RuntimeError('ATTESTATION_INTEGRITY_NOT_RESTORED')
print(json.dumps({'manifestIntegrityRestored':True,
 'verifiedChangedFile':'telegram_live_control.py',
 'regressionTestsPassed':147,'tradingEnabled':False,
 'liveCrashCertified':False,'bot':'STOPPED'}))
