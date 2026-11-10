import unittest
from live_1x_close_guard import evaluate
P={"symbol":"ETHUSDT","side":"LONG","id":"123","manualOrMixed":False}
O={"symbol":"ETHUSDT","positionSide":"LONG"}
BASE=dict(snapshot_fresh=True,preexisting_symbol_free=True,entry_fill_verified=True,order_client_bound=True)
class Tests(unittest.TestCase):
 def test_nominal_still_needs_provenance(self):self.assertEqual(evaluate(P,O,**BASE)["reason"],"EXCHANGE_POSITION_ATTRIBUTION_UNCERTIFIED")
 def test_manual(self):self.assertFalse(evaluate(dict(P,manualOrMixed=True),O,**BASE)["allowed"])
 def test_stale(self):self.assertEqual(evaluate(P,O,**dict(BASE,snapshot_fresh=False))["reason"],"STALE_SNAPSHOT")
 def test_wrong_side(self):self.assertFalse(evaluate(P,dict(O,positionSide="SHORT"),**BASE)["allowed"])
 def test_binding(self):self.assertFalse(evaluate(P,O,**dict(BASE,order_client_bound=False))["allowed"])
if __name__=="__main__":unittest.main()
