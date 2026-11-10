import unittest
from copy import deepcopy
from decimal import Decimal
from weex_quote_semantics_readonly_probe import check
ORDER={'orderId':'1','status':'FILLED','symbol':'BTCUSDT','side':'SELL',
'positionSide':'LONG','executedQty':'3','avgPrice':'8','cumQuote':'24'}
FILLS=[{'id':str(i),'orderId':'1','symbol':'BTCUSDT','side':'SELL','positionSide':'LONG',
 'qty':'1','price':str(p),'quoteQty':str(p),'commission':'0.1','commissionAsset':'USDT'}
 for i,p in ((1,8),(2,9),(3,10))]
class QuoteSemantics(unittest.TestCase):
 def test_alternate_weex_quote_verified(self):
  x=check(ORDER,FILLS)
  self.assertEqual(x['state'],'WEEX_LAST_PRICE_TIMES_QTY_CORROBORATED')
  self.assertEqual(Decimal(x['fillNotional']),27)
 def test_direct_quote_verified(self):
  o={**ORDER,'cumQuote':'27'}
  self.assertEqual(check(o,FILLS)['state'],'DIRECT_QUOTE_MATCH')
 def test_wrong_quote_refused(self):
  self.assertEqual(check({**ORDER,'cumQuote':'26'},FILLS)['state'],'UNEXPLAINED')
 def test_extra_fill_refused(self):
  self.assertEqual(check(ORDER,FILLS+[dict(FILLS[0],id='4')])['state'],'QUANTITY_MISMATCH')
 def test_duplicate_fill_refused(self):
  self.assertEqual(check(ORDER,FILLS+[FILLS[0]])['state'],'DUPLICATE_FILLS')
 def test_wrong_order_id_refused(self):
  rows=deepcopy(FILLS);rows[0]['orderId']='2'
  self.assertEqual(check(ORDER,rows)['state'],'IDENTITY_MISMATCH')
 def test_partial_order_refused(self):
  self.assertEqual(check({**ORDER,'status':'PARTIALLY_FILLED'},FILLS)['state'],'ORDER_NOT_FINAL')
 def test_quote_corrupt_refused(self):
  rows=deepcopy(FILLS);rows[0]['quoteQty']='8.1'
  self.assertEqual(check(ORDER,rows)['state'],'FILL_ECONOMICS_INVALID')
if __name__=='__main__':unittest.main()
