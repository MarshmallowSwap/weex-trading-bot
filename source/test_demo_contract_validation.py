import unittest
from demo_contract_validation import validate
P={"symbol":"BTCSUSDT","side":"BUY","positionSide":"LONG","type":"MARKET","quantity":"0.01","newClientOrderId":"demo_1"}
class Test(unittest.TestCase):
 def test_entry_schema(self):self.assertTrue(validate(P)["valid"])
 def test_no_close_guarantee(self):self.assertFalse(validate(dict(P,side="SELL"),purpose="EXIT")["valid"])
 def test_reduce_only_not_documented(self):self.assertEqual(validate(dict(P,reduceOnly=True))["reason"],"UNDOCUMENTED_FIELDS")
 def test_live_block(self):self.assertFalse(validate(dict(P,symbol="BTCUSDT"))["valid"])
 def test_bad_qty(self):self.assertFalse(validate(dict(P,quantity="NaN"))["valid"])
 def test_limit_requires_price(self):self.assertFalse(validate(dict(P,type="LIMIT",timeInForce="GTC"))["valid"])
if __name__=="__main__":unittest.main()
