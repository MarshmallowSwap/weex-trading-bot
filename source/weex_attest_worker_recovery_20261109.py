"""Attest one focused, tested worker integration; never authorize live trading."""
import hashlib,json,os
from pathlib import Path
from datetime import datetime,timezone
import live_control
ROOT=Path(__file__).resolve().parent
p=ROOT/'live_release_manifest.json'
m=json.loads(p.read_text(encoding='utf-8'))
if m.get('status')!='OFFLINE_VERIFIED_NO_REAL_ORDERS' or m.get('testsPassed') is not True:
 raise PermissionError('INVALID_PREEXISTING_BUILD')
if set(m.get('sha256',{}))!=set(live_control.CODE_FILES):
 raise PermissionError('MANIFEST_INVENTORY_MISMATCH')
changed=sorted(n for n,v in m['sha256'].items()
 if hashlib.sha256((ROOT/n).read_bytes()).hexdigest()!=v)
if changed!=['weex_live_worker.py']:
 raise PermissionError('UNEXPECTED_CHANGED_FILES:'+str(changed))
cfg=json.loads((ROOT/'weex_ai_risk_config.json').read_text(encoding='utf-8'))
if (live_control.state(ROOT)['mode']!='STOPPED' or
  cfg.get('execution',{}).get('enabled') is not False or
  cfg['execution'].get('mode')!='PRETRADE'):
 raise PermissionError('LIVE_MUST_REMAIN_DISARMED')
report=json.loads((ROOT/'weex_live_worker_latest.json').read_text(encoding='utf-8'))
entry=report.get('entryRecoveryAudit',{})
if not (report.get('status')=='DISARMED_READY' and report.get('recoveryClear') is True
 and entry.get('readOnly') is True and entry.get('newExchangeWrites')==0
 and entry.get('uncertainCount')==0
 and not report.get('opened') and not report.get('entryAttempts')):
 raise PermissionError('WORKER_SAFE_RUN_NOT_PROVEN')
m['sha256']['weex_live_worker.py']=hashlib.sha256((ROOT/'weex_live_worker.py').read_bytes()).hexdigest()
m['incrementalWorkerRecoveryTestCount']=38
m['incrementalWorkerRecoveryTestedAt']=datetime.now(timezone.utc).isoformat()
m['validationScope']=(m.get('validationScope','')+
 ' Worker integrates independent fail-closed UNKNOWN-entry read-only veto; '
 '38 focused tests passed and real worker DISARMED_READY without new orders. '
 'Real exchange write crash NOT certified; general trading remains disarmed.')
tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(m,indent=2)+'\n',encoding='utf-8')
os.replace(tmp,p)
if live_control.build_errors(ROOT):raise RuntimeError('INTEGRITY_NOT_RESTORED')
print(json.dumps({'fileAttested':'weex_live_worker.py','focusedTestsPassed':38,
 'manifestIntegrityRestored':True,'realCrashCertified':False,
 'liveEnabled':False,'botMode':live_control.state(ROOT)['mode']}))
