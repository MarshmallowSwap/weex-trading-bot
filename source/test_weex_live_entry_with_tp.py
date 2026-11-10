import unittest
from weex_live_entry_with_tp import build_order,send_order
class Tests(unittest.TestCase):
 def test_inline_tp(self):
  a=build_order(symbol="ETHUSDT",side="LONG",quantity="0.002",price="2300",tp_price="2400",client_order_id="wxpilot_test")
  self.assertEqual(a["tpTriggerPrice"],"2400")
 def test_max_value(self):
  with self.assertRaises(ValueError):build_order(symbol="ETHUSDT",side="LONG",quantity=".1",price="2300",tp_price="2400",client_order_id="wxpilot_test")
 def test_tp_direction(self):
  with self.assertRaises(ValueError):build_order(symbol="ETHUSDT",side="LONG",quantity=".002",price="2300",tp_price="2200",client_order_id="wxpilot_test")
 def test_real_writes_disabled(self):
  a=build_order(symbol="ETHUSDT",side="LONG",quantity=".002",price="2300",tp_price="2400",client_order_id="wxpilot_test")
  with self.assertRaises(PermissionError):send_order(a,client=object(),approval=lambda operation,request:True)
if __name__=="__main__":unittest.main()
