"""Attest only the one tested WEEX accounting gate change.

Validate all untouched protected file hashes before updating the gate hash.
Does not set any gate outcome or enable live orders.
"""
import json,hashlib,os
from pathlib import Path
from datetime import datetime,timezone
import live_control
R=Path(__file__).resolve().parent
p=R/'live_release_manifest.json'
m=json.loads(p.read_text(encoding='utf-8'))
if m.get('status')!='OFFLINE_VERIFIED_NO_REAL_ORDERS' or m.get('testsPassed') is not True:
 raise PermissionError('MANIFEST_PRECONDITIONS_NOT_VERIFIED')
if set(m['sha256'])!=set(live_control.CODE_FILES):
 raise PermissionError('UNEXPECTED_CODE_FILE_INVENTORY')
changed=[name for name,old in m['sha256'].items()
 if hashlib.sha256((R/name).read_bytes()).hexdigest()!=old]
if changed!=['live_release_gate.py']:
 raise PermissionError('UNEXPECTED_CODE_CHANGES:'+str(changed))
if live_control.state(R)['mode']!='STOPPED':
 raise PermissionError('BOT_NOT_STOPPED')
m['sha256']['live_release_gate.py']=hashlib.sha256((R/'live_release_gate.py').read_bytes()).hexdigest()
m['incrementalAccountingPolicyTestCount']=32
m['incrementalAccountingPolicyTestedAt']=datetime.now(timezone.utc).isoformat()
m['validationScope']=('Existing historical testCount is retained as past evidence. '
 'New bounded authenticated income ledger accounting check passed 32 focused '
 'unit/integration tests. Real exchange-write crash NOT tested. '
 'All exchange trading orders remain disabled.')
t=p.with_suffix('.tmp');t.write_text(json.dumps(m,indent=2)+'\n',encoding='utf-8')
os.replace(t,p)
if live_control.build_errors(R):raise RuntimeError('INTEGRITY_NOT_RESTORED')
print(json.dumps({'onlyChangedProtectedFile':'live_release_gate.py',
 'manifestIntegrityRestored':True,'incrementalFocusedTestsPassed':32,
 'originalHistoricSuiteRetained':m['testCount'],
 'liveCrashCertified':False,'botMode':live_control.state(R)['mode'],
 'liveOrdersEnabled':False}))
