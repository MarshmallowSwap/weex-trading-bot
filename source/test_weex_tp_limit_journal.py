"""Offline persistent limit-TP journal tests. No WEEX request."""
import copy,tempfile,unittest
from pathlib import Path
from weex_tp_limit_shadow import propose
from weex_tp_limit_journal import register,observe

class JournalTests(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup)
        self.path=Path(t.name)/'shadow.sqlite3';self.tid='wxentry_0123456789abcdefgh'
        self.proposal=propose(trade_id=self.tid,symbol='ETHUSDT',position_id='p1',
            side='LONG',quantity='2',entry_cost_usdt='200',
            entry_fees_usdt='.16',exit_fee_rate='.0008',
            target_net_usdt='5',price_tick='.01',
            position_observation={'id':'p1','symbol':'ETHUSDT','side':'LONG',
                'size':'2','openValue':'200','openFee':'.16'},
            regular_orders=[],conditional_orders=[])
        r=self.proposal['request']
        self.order={'clientOrderId':r['newClientOrderId'],'symbol':'ETHUSDT',
            'side':'SELL','positionSide':'LONG','type':'LIMIT','reduceOnly':True,
            'price':r['price'],'origQty':'2','executedQty':'0','orderId':'123',
            'status':'NEW'}
    def fill(self,q,idx='one'):
        return {'id':idx,'orderId':'123','side':'SELL','positionSide':'LONG',
            'qty':str(q),'price':self.order['price'],
            'commission':str(float(q)*float(self.order['price'])*.0008),
            'commissionAsset':'USDT'}
    def test_register_restart_idempotent(self):
        self.assertEqual(register(self.path,self.tid,self.proposal)['state'],'PREPARED_NOT_SENT')
        self.assertTrue(register(self.path,self.tid,self.proposal)['alreadyRegistered'])
    def test_immutable_proposal(self):
        register(self.path,self.tid,self.proposal)
        modified=copy.deepcopy(self.proposal);modified['requestedNetUSDT']='99'
        with self.assertRaisesRegex(ValueError,'IMMUTABLE'):
            register(self.path,self.tid,modified)
    def test_unfilled_restart_then_partial_then_closed(self):
        register(self.path,self.tid,self.proposal)
        first=observe(self.path,self.tid,self.order,[],2)
        self.assertEqual(first['state'],'OPEN_UNFILLED')
        self.order.update(executedQty='1',status='PARTIALLY_FILLED')
        second=observe(self.path,self.tid,self.order,[self.fill(1)],1)
        self.assertEqual(second['state'],'PARTIALLY_FILLED')
        self.order.update(executedQty='2',status='FILLED')
        final=observe(self.path,self.tid,self.order,[self.fill(1),self.fill(1,'two')],0)
        self.assertEqual(final['state'],'CLOSED_VERIFIED')
        self.assertTrue(observe(self.path,self.tid,self.order,[],0)['alreadyFinal'])
    def test_wrong_order_id_blocks(self):
        register(self.path,self.tid,self.proposal)
        observe(self.path,self.tid,self.order,[],2)
        bad={**self.order,'orderId':'999'}
        with self.assertRaisesRegex(ValueError,'EXCHANGE_ORDER_ID_CHANGED'):
            observe(self.path,self.tid,bad,[],2)
    def test_changed_price_blocks(self):
        register(self.path,self.tid,self.proposal)
        with self.assertRaisesRegex(ValueError,'ORDER_EVIDENCE_MISMATCH'):
            observe(self.path,self.tid,{**self.order,'price':'1'},[],2)
    def test_executed_qty_disagreement(self):
        register(self.path,self.tid,self.proposal)
        with self.assertRaisesRegex(ValueError,'ORDER_EXECUTED_QUANTITY'):
            observe(self.path,self.tid,{**self.order,'executedQty':'2'},[],2)
    def test_cancelled_requires_review(self):
        register(self.path,self.tid,self.proposal)
        self.assertEqual(observe(self.path,self.tid,{**self.order,'status':'CANCELED'},[],2)['state'],'REVIEW_REQUIRED')
    def test_no_fabricated_send(self):
        with self.assertRaises(ValueError):
            register(self.path,self.tid,{**self.proposal,'dispatchAllowed':True})
    def test_worse_than_limit_rejected(self):
        register(self.path,self.tid,self.proposal)
        self.order.update(executedQty='1',status='PARTIALLY_FILLED')
        bad=self.fill(1);bad['price']='1'
        with self.assertRaisesRegex(ValueError,'EXECUTION_WORSE_THAN_LIMIT'):
            observe(self.path,self.tid,self.order,[bad],1)
    def test_fill_regression_rejected(self):
        register(self.path,self.tid,self.proposal)
        self.order.update(executedQty='1',status='PARTIALLY_FILLED')
        observe(self.path,self.tid,self.order,[self.fill(1)],1)
        self.order.update(executedQty='0',status='NEW')
        with self.assertRaisesRegex(ValueError,'EXECUTION_HISTORY_REGRESSED'):
            observe(self.path,self.tid,self.order,[],2)
if __name__=='__main__':unittest.main()
