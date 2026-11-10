import unittest
from decimal import Decimal
from break_even_resolver import resolve,target_price
class ResolverTests(unittest.TestCase):
 def setUp(self):
  self.p={"side":"LONG","base_quantity":"0.01","avg_entry_price":"65000","allocated_open_fee_usdt":"0.5","net_funding_paid_usdt":"0"}
 def test_calculated_long(self):
  b=resolve(self.p,closing_taker_rate="0.0008")
  self.assertEqual(b.source,"calculated")
  self.assertGreater(b.price,Decimal(65000))
  self.assertGreater(target_price(self.p,b,"1",closing_taker_rate="0.0008"),b.price)
 def test_exchange_precedence(self):
  self.p["exchange_break_even_price"]="65150"
  self.p["exchange_be_includes_exit_costs"]=True
  self.assertEqual(resolve(self.p,closing_taker_rate="0.0008").source,"exchange")
 def test_unverified_exchange_fallback(self):
  self.p["exchange_break_even_price"]="65150"
  self.assertEqual(resolve(self.p,closing_taker_rate="0.0008").source,"calculated")
 def test_short(self):
  self.p["side"]="SHORT"
  b=resolve(self.p,closing_taker_rate="0.0008")
  self.assertLess(b.price,Decimal(65000))
  self.assertLess(target_price(self.p,b,"1",closing_taker_rate="0.0008"),b.price)
if __name__=="__main__":unittest.main()
