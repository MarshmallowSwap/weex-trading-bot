import unittest
from protection_quantity_gate import check
P={"symbol":"BTCUSDT","side":"LONG","size":"2"}
O={"symbol":"BTCUSDT","positionSide":"LONG","status":"NEW","reduceOnly":True,"quantityUnitVerified":True,"quantity":"2"}
class Coverage(unittest.TestCase):
 def test_good(self):self.assertTrue(check(P,[O],True)["covered"])
 def test_missing(self):self.assertFalse(check(P,[],True)["covered"])
 def test_unverified(self):self.assertEqual(check(P,[dict(O,quantityUnitVerified=False)],True)["reason"],"QUANTITY_UNITS_UNVERIFIED")
 def test_partial(self):self.assertEqual(check(P,[dict(O,quantity="1")],True)["reason"],"INSUFFICIENT_COVERAGE")
 def test_pagination(self):self.assertEqual(check(P,[O],False)["reason"],"PAGINATION_INCOMPLETE")
 def test_reduce(self):self.assertEqual(check(P,[dict(O,reduceOnly=False)],True)["reason"],"REDUCE_ONLY_UNVERIFIED")
if __name__=="__main__":unittest.main()
