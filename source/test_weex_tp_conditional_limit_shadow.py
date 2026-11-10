"""WEEX V3 conditional take profit LIMIT no-write tests."""
import unittest
from decimal import Decimal
from weex_tp_conditional_limit_shadow import prepare,inspect_conditional
BASE={'trade_id':'wxentry_012345678901234567890123','symbol':'LTCUSDT','position_id':'p1',
      'side':'LONG','quantity':'94.6','entry_cost_usdt':'5176.461',
      'entry_fees_usdt':'4.1411688','exit_fee_rate':'.0008',
      'target_net_usdt':'15','price_tick':'.01',
      'position_observation':{'id':'p1','symbol':'LTCUSDT','side':'LONG',
          'size':'94.6','openValue':'5176.461','openFee':'4.1411688'},
      'regular_orders':[],'conditional_orders':[]}
class Tests(unittest.TestCase):
 def test_limit_tp_serialized_without_network(self):
  p=prepare(**BASE);r=p['request']
  self.assertEqual(r['executePrice'],'54.97')
  self.assertEqual(r['triggerPrice'],'54.97')
  self.assertEqual(r['planType'],'TAKE_PROFIT')
  self.assertEqual(r['triggerPriceType'],'CONTRACT_PRICE')
  self.assertTrue(r['reduceOnly'])
  self.assertFalse(r['closePosition'])
  self.assertEqual(p['sdkPreview']['networkRequests'],0)
  self.assertFalse(p['dispatchAllowed'])
  self.assertGreaterEqual(Decimal(p['estimatedNetIfFullyExecutedAtLimitUSDT']),15)
 def test_short_fee_adjusted_limit(self):
  b={**BASE,'side':'SHORT','entry_cost_usdt':'5200'}
  b['position_observation']={**BASE['position_observation'],'side':'SHORT','openValue':'5200'}
  r=prepare(**b)['request']
  self.assertLess(Decimal(r['triggerPrice']),Decimal('5200')/Decimal('94.6'))
 def test_copy_key_rejected(self):
  with self.assertRaisesRegex(ValueError,'COPY_TRADING'):
   prepare(**{**BASE,'copy_trading_key':True})
 def test_existing_exit_rejected(self):
  with self.assertRaisesRegex(ValueError,'PREEXISTING_EXIT'):
   prepare(**{**BASE,'conditional_orders':[{'symbol':'LTCUSDT'}]})
 def test_position_change_rejected(self):
  with self.assertRaisesRegex(ValueError,'ENTRY_POSITION_MISMATCH'):
   prepare(**{**BASE,'position_observation':{**BASE['position_observation'],'size':'80'}})
 def test_bad_trigger_source_rejected(self):
  with self.assertRaisesRegex(ValueError,'INVALID_SIDE'):
   prepare(**{**BASE,'trigger_price_type':'OTHER'})
 def test_observed_does_not_certify_sl(self):
  p=prepare(**BASE);r=p['request']
  algo={'algoId':'a1','clientAlgoId':r['clientAlgoId'],'symbol':r['symbol'],
       'positionSide':r['positionSide'],'orderType':'TAKE_PROFIT',
       'reduceOnly':True,'quantity':r['quantity'],
       'triggerPrice':r['triggerPrice'],'price':r['executePrice'],
       'workingType':r['triggerPriceType'],'algoStatus':'UNTRIGGERED'}
  result=inspect_conditional(proposal=p,algo_orders=[algo],
                            position=BASE['position_observation'],sl_orders=[{'algoId':'stop'}])
  self.assertEqual(result['state'],'TP_OBSERVED_SL_COVERAGE_UNVERIFIED')
  self.assertFalse(result['stopLossCompatibilityVerified'])
  self.assertFalse(result['safeToEnterLive'])
  self.assertEqual(inspect_conditional(proposal=p,algo_orders=[algo,algo],
      position=BASE['position_observation'],sl_orders=[])['reason'],'TP_NOT_UNIQUELY_OBSERVED')
 def test_execution_price_mismatch(self):
  p=prepare(**BASE);r=p['request']
  a={'algoId':'a1','clientAlgoId':r['clientAlgoId'],'symbol':r['symbol'],
     'positionSide':r['positionSide'],'orderType':'TAKE_PROFIT','reduceOnly':True,
     'quantity':r['quantity'],'triggerPrice':r['triggerPrice'],'price':'1',
     'workingType':r['triggerPriceType'],'algoStatus':'UNTRIGGERED'}
  self.assertEqual(inspect_conditional(proposal=p,algo_orders=[a],
      position=BASE['position_observation'],sl_orders=[])['reason'],'TP_CONDITIONAL_FIELDS_CHANGED')
if __name__=='__main__':unittest.main()
