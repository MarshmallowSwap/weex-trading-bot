"""Offline negative tests for V6 independent read-only incident handling."""
import json,sqlite3,tempfile,unittest
from contextlib import closing
from pathlib import Path
from weex_independent_incident_supervisor_v6 import decide,observe,EXPECTED_SCOPE
PROOF={"scope":EXPECTED_SCOPE,"status":"PROTECTED_EXACT_CLOSE_READY_FOR_SEPARATE_APPROVAL",
       "positionId":"100","stopAlgoId":"200"}
ACCOUNT={"fresh":True,"oneExactPosition":True,"oneExactStop":True,
         "noOtherOrders":True,"noAdditionalTargetConditional":True,
         "positionId":"100","stopAlgoId":"200"}

class SupervisorV6Tests(unittest.TestCase):
 def test_clean_account_no_pending_crash(self):
  r=decide(control_mode="STOPPED",integrity=True,unknown=False,watchdog={})
  self.assertEqual(r["status"],"NO_PENDING_CRASH_INTENT")
  self.assertFalse(r["releaseCertified"])
 def test_pending_uncertain_is_blocked(self):
  r=decide(control_mode="STOPPED",integrity=True,unknown=True,watchdog=None)
  self.assertTrue(r["manualInterventionRequired"])
  self.assertFalse(r["entryRetryAllowed"])
 def test_verified_protected_never_authorizes_close(self):
  r=decide(control_mode="STOPPED",integrity=True,unknown=True,watchdog=PROOF,account=ACCOUNT)
  self.assertEqual(r["status"],"VERIFIED_PROTECTED_REQUIRES_EXTERNAL_CLOSE_APPROVAL")
  self.assertFalse(r["closeDispatchAllowed"])
 def test_stale_or_mismatched_readback_blocks(self):
  for changed in (dict(ACCOUNT,fresh=False),dict(ACCOUNT,positionId="999"),
                  dict(ACCOUNT,oneExactStop=False),dict(ACCOUNT,noOtherOrders=False)):
   with self.subTest(changed=changed):
    r=decide(control_mode="STOPPED",integrity=True,unknown=True,watchdog=PROOF,account=changed)
    self.assertNotEqual(r["status"],"VERIFIED_PROTECTED_REQUIRES_EXTERNAL_CLOSE_APPROVAL")
    self.assertFalse(r["closeDispatchAllowed"])
 def test_integrity_failure_blocks(self):
  r=decide(control_mode="RUNNING",integrity=False,unknown=True,watchdog=PROOF,account=ACCOUNT)
  self.assertEqual(r["status"],"CRITICAL_PRODUCTION_STATE")
 def test_durable_history_and_no_exchange_writes(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td)
   for _ in range(2):
    r=observe(root,control_fn=lambda:("STOPPED",True),
        unknown_fn=lambda:True,watchdog_fn=lambda:PROOF,account_fn=lambda:ACCOUNT)
    self.assertFalse(r["releaseCertified"])
    self.assertEqual(r["exchangeWrites"],0)
   with closing(sqlite3.connect(root/"weex_supervised_incidents_v6.sqlite3")) as db:
    self.assertEqual(db.execute("SELECT COUNT(*) FROM incidents").fetchone()[0],1)
   self.assertEqual(json.loads((root/"weex_supervised_incident_v6_latest.json").read_text())["status"],
                    "VERIFIED_PROTECTED_REQUIRES_EXTERNAL_CLOSE_APPROVAL")
 def test_observation_exception_blocks(self):
  with tempfile.TemporaryDirectory() as td:
   def bad():raise TimeoutError("sensitive")
   r=observe(td,control_fn=bad)
   self.assertEqual(r["status"],"SUPERVISOR_READBACK_ERROR")
   self.assertNotIn("sensitive",json.dumps(r))
 def test_independent_snapshot_requires_exact_exposure(self):
  from weex_independent_incident_supervisor_v6 import independent_account_snapshot
  class Fake:
   def __init__(self,p,o,a):self.rows=(p,o,a)
   def account(self):return self.rows
  p=[{"symbol":"ETHUSDT","side":"LONG","size":"0.001","id":"100"}]
  a=[{"symbol":"ETHUSDT","side":"SELL","positionSide":"LONG",
      "reduceOnly":True,"quantity":"0.001","algoId":"200"}]
  r=independent_account_snapshot(Path("."),reader=Fake(p,[],a))
  self.assertTrue(r["oneExactPosition"] and r["oneExactStop"] and r["noOtherOrders"])
  foreign_p={"id":"901","symbol":"AINUSDT","side":"SHORT","size":"13200"}
  foreign_tp={"symbol":"AINUSDT","algoId":"902","side":"BUY","positionSide":"SHORT"}
  mixed=independent_account_snapshot(Path("."),reader=Fake([foreign_p]+p,[],[foreign_tp]+a))
  self.assertTrue(mixed["oneExactPosition"] and mixed["oneExactStop"] and mixed["noOtherOrders"])
  self.assertEqual(mixed["positionId"],"100")
  self.assertEqual(mixed["stopAlgoId"],"200")
  self.assertTrue(mixed["foreignExposurePresent"])
  self.assertEqual(mixed["foreignSymbols"],["AINUSDT"])
  for rows in ((p,[{"symbol":"ETHUSDT"}],a),(p,[],a+[dict(a[0],algoId="201")]),
               ([dict(p[0],size="0.01")],[],a)):
   with self.subTest(rows=rows):
    r=independent_account_snapshot(Path("."),reader=Fake(*rows))
    self.assertFalse(r["oneExactPosition"] and r["oneExactStop"] and r["noOtherOrders"])
 def test_supervisor_fails_closed_when_live_readback_throws(self):
  from unittest.mock import patch
  with tempfile.TemporaryDirectory() as td:
   with patch('weex_independent_incident_supervisor_v6.independent_account_snapshot',
              side_effect=TimeoutError("PRIVATE")):
    r=observe(td,control_fn=lambda:("STOPPED",True),unknown_fn=lambda:True,
              watchdog_fn=lambda:PROOF)
   self.assertEqual(r["status"],"SUPERVISOR_READBACK_ERROR")
   self.assertFalse(r["closeDispatchAllowed"])
if __name__=="__main__":unittest.main()
