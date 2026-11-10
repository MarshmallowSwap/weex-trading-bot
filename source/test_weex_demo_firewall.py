import unittest
from weex_demo_firewall import authorize,BASE
class Test(unittest.TestCase):
 def test_live_block(self):self.assertFalse(authorize("POST",BASE+"/capi/v3/order",symbol="BTCUSDT",allow_demo_writes=True)["allowed"])
 def test_demo_symbol(self):self.assertFalse(authorize("POST",BASE+"/capi/v3/sim/order",symbol="BTCUSDT",allow_demo_writes=True)["allowed"])
 def test_read(self):self.assertTrue(authorize("GET",BASE+"/capi/v3/sim/balance")["allowed"])
 def test_demo_write_disabled(self):self.assertFalse(authorize("POST",BASE+"/capi/v3/sim/order",symbol="BTCSUSDT")["allowed"])
 def test_demo_write_allowed(self):self.assertTrue(authorize("POST",BASE+"/capi/v3/sim/order",symbol="BTCSUSDT",allow_demo_writes=True)["allowed"])
 def test_external_block(self):self.assertFalse(authorize("GET","https://fake.example/capi/v3/sim/balance")["allowed"])
if __name__=="__main__":unittest.main()
