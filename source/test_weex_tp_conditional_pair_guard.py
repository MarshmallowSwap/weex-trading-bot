import unittest
from weex_tp_conditional_pair_guard import plan_stop,check_pair
from weex_tp_conditional_limit_shadow import prepare
class PairTests(unittest.TestCase):
 def setUp(self):
  self.position={'id':'p1','symbol':'ETHUSDT','side':'LONG','size':'2','openValue':'200','openFee':'.16'}
  self.tp=prepare(trade_id='wxentry_pair_01',symbol='ETHUSDT',position_id='p1',
      side='LONG',quantity='2',entry_cost_usdt='200',entry_fees_usdt='.16',
      exit_fee_rate='.0008',target_net_usdt='5',price_tick='.01',
      position_observation=self.position,regular_orders=[],conditional_orders=[])
  self.sl=plan_stop(trade_id='wxentry_pair_01',symbol='ETHUSDT',position_side='LONG',
      quantity='2',stop_trigger_price='98',entry_mean_price='100')
  t=self.tp['request'];s=self.sl['request']
  self.algos=[
      {'algoId':'tp-id','clientAlgoId':t['clientAlgoId'],'symbol':'ETHUSDT',
       'positionSide':'LONG','side':'SELL','reduceOnly':True,'quantity':'2',
       'orderType':'TAKE_PROFIT_LIMIT','price':t['executePrice'],
       'triggerPrice':t['triggerPrice'],'workingType':t['triggerPriceType'],
       'algoStatus':'UNTRIGGERED'},
      {'algoId':'sl-id','clientAlgoId':s['clientAlgoId'],'symbol':'ETHUSDT',
       'positionSide':'LONG','side':'SELL','reduceOnly':True,'quantity':'2',
       'orderType':'STOP_LOSS_MARKET','price':'0',
       'triggerPrice':s['triggerPrice'],'workingType':s['triggerPriceType'],
       'algoStatus':'UNTRIGGERED'}]
 def check(self,**kw):
  return check_pair(tp_plan=self.tp,sl_plan=self.sl,position=self.position,
                    observed_algos=self.algos,regular_orders=[],**kw)
 def test_stop_preview_no_network(self):
  self.assertEqual(self.sl['sdkPreview']['networkRequests'],0)
  self.assertEqual(self.sl['request']['executePrice'],'0')
  self.assertFalse(self.sl['dispatchAllowed'])
 def test_identified_pair_does_not_claim_oco(self):
  r=self.check()
  self.assertEqual(r['state'],'PAIR_OBSERVED_NOT_CERTIFIED')
  self.assertFalse(r['ocoCertified']);self.assertFalse(r['liveEntryAllowed'])
 def test_partial_requires_reconcile(self):
  self.position['size']='1'
  self.assertEqual(self.check()['state'],'PARTIAL_POSITION_REQUIRES_EXIT_RECONCILIATION')
 def test_duplicate_tp_rejected(self):
  self.algos.append(dict(self.algos[0]))
  self.assertEqual(self.check()['reason'],'TP_ORDER_MISSING_OR_DUPLICATED')
 def test_market_tp_masquerade_rejected(self):
  self.algos[0]['orderType']='TAKE_PROFIT_MARKET'
  self.assertEqual(self.check()['reason'],'TP_LIMIT_EXECUTION_NOT_CONFIRMED')
 def test_implicit_tp_price_rejected(self):
  self.algos[0].pop('price')
  self.assertEqual(self.check()['reason'],'TP_EXECUTION_PRICE_UNVERIFIED')
 def test_missing_stop_rejected(self):
  self.algos.pop()
  self.assertEqual(self.check()['reason'],'SL_ORDER_MISSING_OR_DUPLICATED')
 def test_stop_price_market_only(self):
  self.algos[1]['price']='96'
  self.assertEqual(self.check()['reason'],'STOP_NOT_MARKET_EXECUTION')
 def test_stop_wrong_side(self):
  self.algos[1]['side']='BUY'
  self.assertEqual(self.check()['reason'],'SL_ORDER_FIELDS_CHANGED')
 def test_unexpected_regular_order(self):
  r=check_pair(tp_plan=self.tp,sl_plan=self.sl,position=self.position,
               observed_algos=self.algos,regular_orders=[{'symbol':'ETHUSDT'}])
  self.assertEqual(r['reason'],'UNACCOUNTED_REGULAR_EXIT_ORDER')
 def test_stop_wrong_direction(self):
  with self.assertRaisesRegex(ValueError,'STOP_NOT_ADVERSE'):
   plan_stop(trade_id='a',symbol='ETHUSDT',position_side='LONG',quantity=2,
             stop_trigger_price='101',entry_mean_price='100')
 def test_short_stop_above_entry(self):
  stop=plan_stop(trade_id='a',symbol='ETHUSDT',position_side='SHORT',
                 quantity='2',stop_trigger_price='102',entry_mean_price='100')
  self.assertEqual(stop['request']['triggerPrice'],'102')
 def test_changed_position_refused(self):
  self.position['side']='SHORT'
  self.assertEqual(self.check()['reason'],'POSITION_IDENTITY_CHANGED')
if __name__=='__main__':unittest.main()
