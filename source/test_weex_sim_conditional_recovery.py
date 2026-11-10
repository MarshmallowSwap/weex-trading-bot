import tempfile,unittest
from pathlib import Path
from weex_sim_conditional_recovery import register,observe
class Recovery(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.db=str(Path(self.tmp.name)/'ledger.sqlite')
  self.args=dict(position_id=123,symbol='BTCUSDT',side='LONG',
      entry_quantity='2',tp_client_id='tp123',sl_client_id='sl123',
      entry_cost='200',entry_fees='.16')
  register(self.db,'tradeA',**self.args)
  self.position=[dict(id=123,symbol='BTCUSDT',side='LONG',size='2')]
  self.algos=[
      dict(clientAlgoId='tp123',symbol='BTCUSDT',positionSide='LONG',
           side='SELL',reduceOnly=True,quantity='2',orderType='TAKE_PROFIT_LIMIT',
           price='110',algoStatus='UNTRIGGERED'),
      dict(clientAlgoId='sl123',symbol='BTCUSDT',positionSide='LONG',
           side='SELL',reduceOnly=True,quantity='2',orderType='STOP_LOSS_MARKET',
           price='0',algoStatus='UNTRIGGERED')]
  self.fills=[]
 def check(self,**kw):
  return observe(self.db,'tradeA',positions=kw.get('positions',self.position),
      algos=kw.get('algos',self.algos),regular_orders=kw.get('regular_orders',[]),
      exit_fills=kw.get('exit_fills',self.fills),source_confirmed=kw.get('source_confirmed',True))
 def fill(self,q='1'):
  return dict(id='f1',positionId=123,symbol='BTCUSDT',positionSide='LONG',
       side='SELL',commissionAsset='USDT',qty=q,price='110',commission='.08')
 def test_dual_algos_not_certified(self):
  r=self.check()
  self.assertEqual(r['state'],'BOTH_ALGOS_OBSERVED_NOT_OCO_CERTIFIED')
  self.assertFalse(r['ocoCertified']);self.assertFalse(r['actionsAllowed'])
 def test_missing_stop_review(self):
  self.algos=self.algos[:1]
  self.assertEqual(self.check()['state'],'MISSING_PROTECTION_REVIEW')
 def test_partial_needs_reconciliation(self):
  self.position[0]['size']='1';self.fills=[self.fill()]
  r=self.check()
  self.assertEqual(r['state'],'PARTIAL_RECONCILIATION_REQUIRED')
  self.assertEqual(float(r['evidence']['realizedNetBeforeFundingUSDT']),9.84)
  self.assertFalse(r['canRetry'])
 def test_restart_does_not_reset_progress(self):
  self.position[0]['size']='1';self.fills=[self.fill()]
  self.check()
  self.assertTrue(register(self.db,'tradeA',**self.args)['existing'])
  self.position[0]['size']='2';self.fills=[]
  self.assertEqual(self.check()['reason'],'RESTART_FILL_REGRESSION')
 def test_changed_intent_blocks(self):
  with self.assertRaisesRegex(ValueError,'RESTART_INTENT_CHANGED'):
   register(self.db,'tradeA',**{**self.args,'entry_quantity':'3'})
 def test_missing_fill_does_not_count_closed(self):
  self.position=[]
  self.assertEqual(self.check()['reason'],'FILLS_AND_REMAINING_DISAGREE')
 def test_closed_but_orphan_exits(self):
  self.position=[];self.fills=[self.fill('2')]
  self.assertEqual(self.check()['reason'],'ORPHANED_EXITS_AFTER_CLOSE')
 def test_closed_clean(self):
  self.position=[];self.fills=[self.fill('2')];self.algos=[]
  r=self.check()
  self.assertEqual(r['state'],'CLOSED_READBACK_NO_OCO_PROOF')
  self.assertEqual(float(r['evidence']['realizedNetBeforeFundingUSDT']),19.76)
 def test_duplicate_fill_blocks(self):
  self.position[0]['size']='0';self.fills=[self.fill(),self.fill()]
  self.assertEqual(self.check()['reason'],'DUPLICATE_FILL_ID')
 def test_unknown_order_blocks(self):
  self.assertEqual(self.check(regular_orders=[{'symbol':'BTCUSDT'}])['reason'],'UNKNOWN_REGULAR_ORDER')
 def test_wrong_position_id_blocks(self):
  self.position[0]['id']=999
  self.assertEqual(self.check()['reason'],'FILLS_AND_REMAINING_DISAGREE')
 def test_unverified_readback_blocks(self):
  self.assertEqual(self.check(source_confirmed=False)['reason'],'EXCHANGE_READBACK_NOT_CONFIRMED')
 def test_stop_inactive_blocks(self):
  self.algos[1]['algoStatus']='CANCELED'
  self.assertEqual(self.check()['reason'],'SL_ORDER_CHANGED_OR_INACTIVE')
 def test_wrong_tp_type_is_not_accepted(self):
  self.algos[0]['orderType']='TAKE_PROFIT_MARKET'
  self.assertEqual(self.check()['reason'],'TP_ORDER_TYPE_UNVERIFIED')
 def test_stop_market_price_cannot_be_limit(self):
  self.algos[1]['price']='98'
  self.assertEqual(self.check()['reason'],'STOP_MARKET_EXECUTION_UNVERIFIED')
 def test_stop_missing_reduce_only_refused(self):
  self.algos[1]['reduceOnly']=False
  self.assertEqual(self.check()['reason'],'SL_ORDER_CHANGED_OR_INACTIVE')
 def test_wrong_stop_quantity_refused(self):
  self.algos[1]['quantity']='1'
  self.assertEqual(self.check()['reason'],'SL_ORDER_QUANTITY_CHANGED')
 def test_tp_limit_without_limit_price_refused(self):
  del self.algos[0]['price']
  self.assertEqual(self.check()['reason'],'TP_LIMIT_EXECUTION_PRICE_UNVERIFIED')
if __name__=='__main__':unittest.main()
