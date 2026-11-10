import unittest
from weex_demo_firewall import authorize,BASE
class Tests(unittest.TestCase):
 def test_btc(self):self.assertTrue(authorize("POST",BASE+"/capi/v3/sim/order","BTCSUSDT",True)["allowed"])
 def test_false_suffix(self):self.assertFalse(authorize("POST",BASE+"/capi/v3/sim/order","GASUSDT",True)["allowed"])
 def test_live(self):self.assertFalse(authorize("POST",BASE+"/capi/v3/order","BTCUSDT",True)["allowed"])
 def test_disabled(self):self.assertFalse(authorize("POST",BASE+"/capi/v3/sim/order","BTCSUSDT",False)["allowed"])
 def test_read(self):self.assertTrue(authorize("GET",BASE+"/capi/v3/sim/balance")["allowed"])
if __name__=="__main__":unittest.main()
