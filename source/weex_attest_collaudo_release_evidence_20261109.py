"""Attest fail-closed worker crash evidence gate and repeatable read-only COLLAUDO.
Never send orders or modify the requested trading/risk strategy.
"""
import hashlib,json,os,subprocess,sys
from pathlib import Path
from datetime import datetime,timezone
import live_control
from weex_real_worker_crash_evidence_gate import certify

ROOT=Path(__file__).resolve().parent
manifest=ROOT/'live_release_manifest.json'
m=json.loads(manifest.read_text(encoding='utf-8'))
assert m.get('status')=='OFFLINE_VERIFIED_NO_REAL_ORDERS'
assert m.get('testsPassed') is True
assert live_control.state(ROOT)['mode']=='STOPPED'
risk=json.loads((ROOT/'weex_ai_risk_config.json').read_text(encoding='utf-8'))
assert risk['execution']['enabled'] is False and risk['execution']['mode']=='PRETRADE'
added={'weex_real_worker_crash_evidence_gate.py','weex_telegram_collaudo.py',
 'weex_collaudo_refresh_readonly.py','weex_worker_crash_probe_test_20261109.py',
 'weex_final_live_status_readonly_20261109.py'}
previous=set(m['sha256'])
current=set(live_control.CODE_FILES)
assert current-previous==added,(current-previous)
assert previous-current==set()
changed={name for name in previous if
 hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=m['sha256'][name]}
assert changed=={'live_control.py','live_release_gate.py'},changed
assert certify(ROOT).get('certified') is False
tests=subprocess.run([sys.executable,'-m','unittest','-q',
 'test_live_control_release_gate','test_live_release_gate',
 'test_weex_real_worker_crash_evidence_gate','test_weex_telegram_collaudo',
 'test_weex_worker_recovery_integration_20261109',
 'test_weex_full_lifecycle_os_crash_drill','test_weex_lifecycle'],
 cwd=ROOT,capture_output=True,text=True,timeout=90)
assert tests.returncode==0 and 'Ran 73 tests' in tests.stderr,tests.stderr[-800:]
for name in sorted(added|changed):
 m['sha256'][name]=hashlib.sha256((ROOT/name).read_bytes()).hexdigest()
m['crashEvidenceGateRevision']={'at':datetime.now(timezone.utc).isoformat(),
 'scope':'REAL_WORKER_SQLITE_JOURNAL_AND_INDEPENDENT_PRODUCTION_API_GET',
 'oldHardcodedFalseReplaced':True,'attestationPresent':False,
 'currentRealCrashCertified':False,'regressionTestsPassed':73,
 'telegramReadOnlyRefreshSteps':6,'realOrdersSubmitted':0}
m['validationScope']=m.get('validationScope','')+(
 ' Crash gate now checks exact production worker durable UNKNOWN intent, matching'
 ' live WEEX entry/fills, native attached stop, reduce-only exit and flat account;'
 ' rejects demo/read-side evidence and absent attestation. 73 focused tests.'
 ' COLLAUDO refreshes read-only release prerequisites. No real order or GO claim.')
tmp=manifest.with_suffix('.tmp')
tmp.write_text(json.dumps(m,indent=2)+'\n',encoding='utf-8')
os.replace(tmp,manifest)
assert not live_control.build_errors(ROOT),live_control.build_errors(ROOT)
print(json.dumps({'status':'MANIFEST_ATTESTED','tests':73,'integrity':'PASS',
 'realCrashCertified':False,'liveEnabled':False,'filesAdded':len(added),
 'filesUpdated':len(changed)}))
