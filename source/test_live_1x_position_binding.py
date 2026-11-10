import unittest
from live_1x_position_binding import reconcile_position
P={"symbol":"ETHUSDT","side":"LONG","positionId":"123","manualOrMixed":False}
O={"symbol":"ETHUSDT","positionSide":"LONG","verified":True,"status":"FILLED","clientOrderId":"x","orderId":"w"}
class Test(unittest.TestCase):
 def test_candidate_not_certified(self):
  r=reconcile_position(P,O,manual_exposure_before=False,fresh_snapshot=True)
  self.assertFalse(r["verified"]);self.assertFalse(r["closeAuthorized"])
 def test_manual_unknown(self):
  self.assertEqual(reconcile_position(P,O,manual_exposure_before=None,fresh_snapshot=True)["reason"],"PREEXISTING_EXPOSURE_UNKNOWN")
 def test_stale(self):
  self.assertFalse(reconcile_position(P,O,manual_exposure_before=False,fresh_snapshot=False)["verified"])
 def test_symbol(self):
  self.assertFalse(reconcile_position(P,dict(O,symbol="BTCUSDT"),manual_exposure_before=False,fresh_snapshot=True)["verified"])
if __name__=="__main__":unittest.main()
