import unittest
from weex_economic_fills_readonly import audit

def order(**changes):
    base={'orderId':'1','symbol':'ETHUSDT','status':'FILLED','side':'BUY',
          'positionSide':'LONG','executedQty':'0.002','avgPrice':'2000',
          'cumQuote':'4'}
    return {**base,**changes}
def fill(**changes):
    base={'id':'f1','orderId':'1','symbol':'ETHUSDT','side':'BUY',
          'positionSide':'LONG','qty':'0.002','price':'2000',
          'quoteQty':'4','commission':'0.002','commissionAsset':'USDT'}
    return {**base,**changes}

class EconomicEvidenceTests(unittest.TestCase):
 def test_exact_quote_match(self):
    r=audit([order()],[fill()])
    self.assertEqual(r['ordersWithEconomicEvidence'],1)
    self.assertTrue(r['allBoundedOrderEconomicsVerified'])
    self.assertFalse(r['liveGoCertified'])
 def test_missing_order_never_proven(self):
    r=audit([],[fill()])
    self.assertEqual(r['unverifiedOrders'][0]['state'],'ORDER_NOT_IN_HISTORY')
    self.assertFalse(r['allBoundedOrderEconomicsVerified'])
 def test_canceled_order_with_fill_not_proven(self):
    r=audit([order(status='CANCELED')],[fill()])
    self.assertEqual(r['unverifiedOrders'][0]['state'],'ORDER_NOT_FINAL')
 def test_incomplete_fill_not_proven(self):
    r=audit([order(executedQty='0.004')],[fill()])
    self.assertEqual(r['unverifiedOrders'][0]['state'],'INCOMPLETE_ORDER_FILLS')
 def test_inconsistent_quote_not_proven(self):
    r=audit([order(cumQuote='5')],[fill()])
    self.assertEqual(r['unverifiedOrders'][0]['state'],'UNEXPLAINED')
if __name__=='__main__':unittest.main()
