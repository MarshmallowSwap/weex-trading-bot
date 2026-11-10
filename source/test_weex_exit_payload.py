import unittest
from weex_exit_payload import make_tp_sl
BASE=dict(symbol="BTCUSDT",position_side="LONG",quantity="0.01239",step="0.0001",tick="0.1",trigger="81000.0",client_algo_id="tp-test-123")
class Tests(unittest.TestCase):
 def test_floor_quantity(self):
  a=make_tp_sl(**BASE);self.assertEqual(a["quantity"],"0.0123");self.assertTrue(a["reduceOnly"])
 def test_oneway_rejected(self):
  with self.assertRaises(ValueError):make_tp_sl(**dict(BASE,position_mode="ONE_WAY"))
 def test_small_rejected(self):
  with self.assertRaises(ValueError):make_tp_sl(**dict(BASE,quantity="0.00001"))
 def test_invalid_tick(self):
  with self.assertRaises(ValueError):make_tp_sl(**dict(BASE,trigger="81000.03"))
 def test_invalid_id(self):
  with self.assertRaises(ValueError):make_tp_sl(**dict(BASE,client_algo_id="invalid space"))
if __name__=="__main__":unittest.main()
