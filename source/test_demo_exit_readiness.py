import unittest
from demo_exit_readiness import check
P={"symbol":"BTCSUSDT","side":"LONG","size":"0.01","marginType":"CROSSED","ownershipVerified":True,"manualOrMixed":False,"originClientOrderId":"bot1"}
class T(unittest.TestCase):
 def test_no_exit_proof(self):self.assertEqual(check(P,{"bot1"})["reason"],"DEMO_CLOSE_NOT_CERTIFIED")
 def test_manual(self):self.assertFalse(check(dict(P,manualOrMixed=True),{"bot1"},demo_close_verified=True)["allowed"])
 def test_unknown_owner(self):self.assertFalse(check(dict(P,ownershipVerified=False),{"bot1"},demo_close_verified=True)["allowed"])
 def test_long(self):self.assertEqual(check(P,{"bot1"},demo_close_verified=True)["closingSide"],"SELL")
 def test_short(self):self.assertEqual(check(dict(P,side="SHORT"),{"bot1"},demo_close_verified=True)["closingSide"],"BUY")
 def test_live_pair(self):self.assertFalse(check(dict(P,symbol="BTCUSDT"),{"bot1"},demo_close_verified=True)["allowed"])
 def test_wrong_mode(self):self.assertFalse(check(dict(P,marginType="ISOLATED"),{"bot1"},demo_close_verified=True)["allowed"])
if __name__=="__main__":unittest.main()
