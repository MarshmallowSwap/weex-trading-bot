import unittest
from weex_live_preflight import fresh_order,verify_after_submit
Q={"symbol":"ETHUSDT","bid":"2350","ask":"2350.5","timestampMs":10000}
P={"symbol":"ETHUSDT","side":"LONG","quantity":"0.002","tp_price":"2450","client_order_id":"wxpilot_test","now_ms":10001}
class Tests(unittest.TestCase):
 def test_fresh(self):self.assertEqual(fresh_order(quote=Q,**P)["type"],"MARKET")
 def test_stale(self):
  with self.assertRaisesRegex(ValueError,"STALE"):fresh_order(quote=Q,**dict(P,now_ms=20000))
 def test_cap(self):
  with self.assertRaisesRegex(ValueError,"NOTIONAL"):fresh_order(quote=Q,**dict(P,quantity=".003"))
 def test_no_ack(self):self.assertEqual(verify_after_submit(client_order_id="c",ack={},orders=[],positions=[],tp_orders=[])["state"],"UNKNOWN_EXECUTION")
 def test_legacy_synthetic_fields_do_not_certify_position(self):
  self.assertEqual(verify_after_submit(client_order_id="c",ack={"orderId":"1"},orders=[{"orderId":"1","clientOrderId":"c","symbol":"ETHUSDT"}],positions=[{"symbol":"ETHUSDT","entryOrderId":"1"}],tp_orders=[])["state"],"RECONCILIATION_REQUIRED")
if __name__=="__main__":unittest.main()
