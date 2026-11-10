import hashlib,json,tempfile,unittest
from unittest.mock import patch
from datetime import datetime,timedelta,timezone
from pathlib import Path
from live_control import build_errors,readiness,release_gate_errors

class ReleaseGateTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
  self.now=datetime.now(timezone.utc)
 def write(self,data):
  (self.root/"live_release_gate_latest.json").write_text(json.dumps(data),encoding="utf-8")
 def test_fresh_complete_go_passes(self):
  self.write({"checkedAt":self.now.isoformat(),"gate":"GO","checks":{"a":True,"b":True},
              "passed":2,"total":2,"ordersPlacedByAudit":False})
  self.assertEqual(release_gate_errors(self.root,now=self.now.timestamp()),[])
 def test_no_go_blocks(self):
  self.write({"checkedAt":self.now.isoformat(),"gate":"NO_GO","checks":{"a":False},
              "passed":0,"total":1,"ordersPlacedByAudit":False})
  self.assertEqual(release_gate_errors(self.root,now=self.now.timestamp()),["LIVE_RELEASE_NO_GO"])
 def test_stale_gate_blocks(self):
  old=(self.now-timedelta(minutes=11)).isoformat()
  self.write({"checkedAt":old,"gate":"GO","checks":{"a":True},"passed":1,"total":1,"ordersPlacedByAudit":False})
  self.assertEqual(release_gate_errors(self.root,now=self.now.timestamp()),["LIVE_RELEASE_GATE_STALE"])
 def test_missing_gate_fails_closed(self):
  self.assertEqual(release_gate_errors(self.root,now=self.now.timestamp()),["LIVE_RELEASE_GATE_UNAVAILABLE"])

class RuntimeReleaseTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
  (self.root/'module.py').write_text('verified code',encoding='utf-8')
  manifest={'status':'OFFLINE_VERIFIED_NO_REAL_ORDERS','testsPassed':True,
            'sha256':{'module.py':hashlib.sha256(b'verified code').hexdigest()}}
  (self.root/'live_release_manifest.json').write_text(json.dumps(manifest),encoding='utf-8')
  self.patch=patch('live_control.CODE_FILES',('module.py',));self.patch.start();self.addCleanup(self.patch.stop)
 def test_historical_gate_does_not_block_verified_build(self):
  self.assertEqual(build_errors(self.root),[])
  for gate in ('GO','NO_GO'):
   (self.root/'live_release_gate_latest.json').write_text(json.dumps({
    'checkedAt':'2000-01-01T00:00:00+00:00','gate':gate,
    'checks':{'crash_restart_recovery_live_tested':False}}),encoding='utf-8')
   self.assertEqual(build_errors(self.root),[])
 def test_modified_code_still_blocks(self):
  (self.root/'module.py').write_text('changed',encoding='utf-8')
  self.assertEqual(build_errors(self.root),['CODICE_MODIFICATO_DOPO_COLLAUDO'])
 def test_missing_manifest_still_blocks(self):
  (self.root/'live_release_manifest.json').unlink()
  self.assertEqual(build_errors(self.root),['COLLAUDO_NON_DISPONIBILE'])
 def test_current_account_recovery_failure_still_blocks(self):
  (self.root/'weex_live_worker_latest.json').write_text(json.dumps({
    'checkedAt':datetime.now(timezone.utc).isoformat(),'accountReadOK':True,
    'recoveryClear':False,'host':'https://api-contract.weex.com'}),encoding='utf-8')
  with patch('live_control.configuration',return_value=({},'digest')):
   self.assertIn('CONTO_O_RECUPERO_DA_VERIFICARE',readiness(self.root))

if __name__=="__main__":unittest.main()
