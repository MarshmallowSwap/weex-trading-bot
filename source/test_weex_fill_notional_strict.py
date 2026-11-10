import unittest
from weex_fill_notional_strict import verify
def fixture():
 o={'orderId':'7','symbol':'TRUTHUSDT','side':'SELL','positionSide':'SHORT',
    'status':'FILLED','executedQty':'80000','cumQuote':'1433.76','avgPrice':'0.017922'}
 f=[{'id':'f','orderId':'7','symbol':'TRUTHUSDT','side':'SELL','positionSide':'SHORT',
     'qty':'80000','price':'0.017921000000125','quoteQty':'1433.68000001',
     'commission':'0','commissionAsset':'USDT'}]
 return o,f
class StrictFill(unittest.TestCase):
 def test_realistic_rounding_preserves_fill_notional(self):
  o,f=fixture();r=verify(o,f);self.assertTrue(r['verified'],r)
  self.assertEqual(r['executedFillNotionalUSDT'],'1433.68000001')
  self.assertFalse(r['parentCumQuoteEqualFillSum'])
  self.assertTrue(r['parentCumQuoteEqualReportedAvgTimesQty'])
  self.assertFalse(r['liveGoCertified'])
 def test_uai_precision(self):
  o,f=fixture();o.update(symbol='UAIUSDT',executedQty='20050',
      cumQuote='2209.51',avgPrice='0.1102')
  f[0].update(symbol='UAIUSDT',qty='20050',price='0.1101000000004988',
      quoteQty='2207.50500001')
  r=verify(o,f);self.assertTrue(r['verified'],r)
  self.assertEqual(r['parentOrderQuoteDifferenceUSDT'],'2.00499999')
 def test_reject_other_order(self):
  o,f=fixture();f[0]['orderId']='another'
  self.assertFalse(verify(o,f)['verified'])
 def test_reject_bad_quote(self):
  o,f=fixture();f[0]['quoteQty']='1400'
  self.assertFalse(verify(o,f)['verified'])
 def test_reject_duplicate_fills(self):
  o,f=fixture();self.assertFalse(verify(o,f+f)['verified'])
 def test_reject_partial_history(self):
  o,f=fixture();self.assertFalse(verify(o,[])['verified'])
 def test_reject_wrong_fee_currency(self):
  o,f=fixture();f[0]['commissionAsset']='BTC'
  self.assertFalse(verify(o,f)['verified'])
if __name__=='__main__':unittest.main()
