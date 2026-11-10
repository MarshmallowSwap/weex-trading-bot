import unittest
from unittest.mock import patch
import demo_submission_controller as c
P={"symbol":"BTCSUSDT","side":"BUY","positionSide":"LONG","type":"MARKET","quantity":"0.01"}
class Tests(unittest.TestCase):
 def test_all_true_flags_cannot_bypass(self):
  self.assertFalse(c.attempt(P,exit_verified=True,binding_verified=True)["submitted"])
 def test_fake_certification_still_no_send(self):
  with patch.object(c,"evidence_run",return_value={"ready":True,"checks":{}}):
   self.assertEqual(c.attempt(P,exit_verified=True,binding_verified=True)["reason"],"DEMO_TRANSPORT_DISABLED")
 def test_missing_evidence(self):
  with patch.object(c,"evidence_run",return_value={"ready":False,"checks":{"demo_close_verified":False}}):
   self.assertIn("demo_close_verified",c.attempt(P)["failedChecks"])
if __name__=="__main__":unittest.main()
