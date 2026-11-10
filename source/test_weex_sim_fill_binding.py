import unittest
from weex_sim_fill_binding import bind_exit_fills
from weex_sim_conditional_recovery import register,observe
from pathlib import Path
from tempfile import TemporaryDirectory
P={'position_id':'123','symbol':'BTCUSDT','side':'LONG','verified_exit_order_ids':{'981'},
   'raw_fills':[{'id':111,'orderId':981,'symbol':'BTCUSDT','positionSide':'LONG',
      'side':'SELL','commissionAsset':'USDT','qty':'1','price':'110','commission':'.08'}],
   'order_history':[{'orderId':981,'symbol':'BTCUSDT','positionSide':'LONG',
      'side':'SELL','reduceOnly':True,'executedQty':'1'}]}
class Tests(unittest.TestCase):
 def test_weex_actual_schema_missing_position_id_bound_through_order(self):
  r=bind_exit_fills(**P)
  self.assertFalse(r['exchangePositionIdPresent'])
  self.assertEqual(r['normalized'][0]['positionId'],'123')
  self.assertFalse(r['ordersSubmitted'])
 def test_unverified_order_missing_history(self):
  with self.assertRaisesRegex(ValueError,'VERIFIED_ORDERS_MISSING'):
   bind_exit_fills(**{**P,'order_history':[]})
 def test_wrong_direction_blocks(self):
  with self.assertRaisesRegex(ValueError,'VERIFIED_ORDER_NOT_CLOSE_ONLY'):
   bind_exit_fills(**{**P,'order_history':[{**P['order_history'][0],'side':'BUY'}]})
 def test_reduce_only_required(self):
  with self.assertRaisesRegex(ValueError,'VERIFIED_ORDER_NOT_CLOSE_ONLY'):
   bind_exit_fills(**{**P,'order_history':[{**P['order_history'][0],'reduceOnly':False}]})
 def test_missing_fill_not_silently_accepted(self):
  with self.assertRaisesRegex(ValueError,'INCOMPLETE_OR_REGRESSED'):
   bind_exit_fills(**{**P,'raw_fills':[]})
 def test_fill_from_unrelated_order_not_attributed(self):
  r=bind_exit_fills(**{**P,'raw_fills':P['raw_fills']+[{**P['raw_fills'][0],'orderId':99,'id':222}]})
  self.assertEqual(len(r['normalized']),1)
 def test_conflicting_position_id_refused(self):
  with self.assertRaisesRegex(ValueError,'CONFLICTING_FILL_POSITION'):
   bind_exit_fills(**{**P,'raw_fills':[{**P['raw_fills'][0],'positionId':'999'}]})
 def test_duplicate_fills_refused(self):
  with self.assertRaisesRegex(ValueError,'DUPLICATED_OR_MISSING_FILL'):
   bind_exit_fills(**{**P,'raw_fills':P['raw_fills']*2,'order_history':[{**P['order_history'][0],'executedQty':'2'}]})
 def test_recovery_integration_with_verified_order_binding(self):
  r=bind_exit_fills(**P)
  with TemporaryDirectory() as tmp:
   database=str(Path(tmp)/'audit.sqlite')
   register(database,'t',position_id=123,symbol='BTCUSDT',side='LONG',
            entry_quantity='2',tp_client_id='tp',sl_client_id='sl',
            entry_cost='200',entry_fees='.16')
   positions=[{'id':123,'symbol':'BTCUSDT','side':'LONG','size':'1'}]
   algos=[{'clientAlgoId':'tp','symbol':'BTCUSDT','positionSide':'LONG',
           'side':'SELL','reduceOnly':True,'quantity':'2','orderType':'TAKE_PROFIT_LIMIT',
           'price':'110','algoStatus':'UNTRIGGERED'},
          {'clientAlgoId':'sl','symbol':'BTCUSDT','positionSide':'LONG',
           'side':'SELL','reduceOnly':True,'quantity':'2','orderType':'STOP_LOSS_MARKET',
           'price':'0','algoStatus':'UNTRIGGERED'}]
   observed=observe(database,'t',positions=positions,algos=algos,regular_orders=[],
                   exit_fills=r['normalized'],source_confirmed=True)
   self.assertEqual(observed['state'],'PARTIAL_RECONCILIATION_REQUIRED')
   self.assertFalse(observed['actionsAllowed'])
if __name__=='__main__':unittest.main()
