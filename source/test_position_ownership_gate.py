import unittest
from position_ownership_gate import authorize
P={"symbol":"BTCUSDT","positionSide":"LONG","manualOrMixed":False}
B=[{"symbol":"BTCUSDT","positionSide":"LONG","source":"BOT","exchangeOrderId":"ex1","clientOrderId":"bot1","verified":True}]
class Tests(unittest.TestCase):
 def test_manual(self):self.assertFalse(authorize("CLOSE",dict(P,manualOrMixed=True),B,reconciled=True)["allowed"])
 def test_unbound(self):self.assertFalse(authorize("CLOSE",P,[],reconciled=True)["allowed"])
 def test_unknown_mix(self):self.assertFalse(authorize("CLOSE",{k:v for k,v in P.items() if k!="manualOrMixed"},B,reconciled=True)["allowed"])
 def test_unreconciled(self):self.assertFalse(authorize("CLOSE",P,B,reconciled=False)["allowed"])
 def test_bot_verified(self):self.assertTrue(authorize("CLOSE",P,B,reconciled=True)["allowed"])
 def test_duplicate(self):self.assertFalse(authorize("CLOSE",P,B+B,reconciled=True)["allowed"])
 def test_monitor(self):self.assertTrue(authorize("MONITOR",P,[])["allowed"])
if __name__=="__main__":unittest.main()
