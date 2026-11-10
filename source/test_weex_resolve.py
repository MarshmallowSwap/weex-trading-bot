import copy,json,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
import test_weex_reconcile as base
from test_weex_reconcile import fixture
import weex_reconcile as module

class ResolveTests(unittest.TestCase):
    setUp=base.ReconcileTests.setUp
    insert_item=base.ReconcileTests.insert_item
    run_job=base.ReconcileTests.run_job
    def setup_exit(self,trailing=False,child=False):
        self.item,self.orders,self.fills,self.rows=fixture(short=True,trailing=trailing)
        self.insert_item();algo=copy.deepcopy(self.rows[2][0]);self.rows[2]=[]
        algo.update(algoStatus='FILLED',status='FILLED',actualOrderId='4' if child else None)
        close=self.orders.pop();close.update(orderId='4' if child else '2',
            clientOrderId='child' if child else 'wxtp_fixture',
            type='MARKET' if child else ('TRAILING_MARKET' if trailing else 'TAKE_PROFIT_MARKET'))
        fs=self.fills.pop('3');fs[0].update(orderId=close['orderId']);self.fills[close['orderId']]=fs
        def read(op,**q):
            if op=='get_capi_v3_order_history':return copy.deepcopy(self.orders)
            if op=='get_capi_v3_allAlgoOrders':return {'orders':[] if trailing else [copy.deepcopy(algo)],'hasMore':False}
            if op=='get_capi_v3_trailing_historyOrders':return [copy.deepcopy(algo)] if trailing else []
            if op=='get_capi_v3_order':return copy.deepcopy(close if str(q['orderId'])==close['orderId'] else self.orders[0])
            if op=='get_capi_v3_userTrades':return copy.deepcopy(self.fills[str(q['orderId'])])
            raise AssertionError(op)
        self.reader.read.side_effect=read
        return algo,close
    def test_fixed_tp_missing_from_regular_history_is_resolved(self):
        self.setup_exit();result=self.run_job()
        self.assertEqual(result['status'],'DONE',result);self.assertFalse(self.calls)
        self.assertEqual(result['items'][0]['state'],'CLOSED_BOT_TP')
        self.assertTrue(self.engine.get(self.item['id'])['detail']['botTPUsed'])
    def test_child_order_bound_to_actual_order_id(self):
        self.setup_exit(child=True);result=self.run_job()
        self.assertEqual(result['status'],'DONE',result)
        self.assertEqual(self.engine.get(self.item['id'])['detail']['exitOrderIds'],['4'])
    def test_native_trailing_history_is_included(self):
        self.setup_exit(trailing=True);result=self.run_job()
        self.assertEqual(result['status'],'DONE',result);self.assertFalse(self.calls)
    def test_changed_historical_tp_parameters_are_rejected(self):
        algo,close=self.setup_exit();algo['triggerPrice']='999'
        result=self.run_job();self.assertEqual(result['items'][0]['reason'],'BOT_TP_HISTORY_MISMATCH')
        self.assertEqual(self.engine.get(self.item['id'])['state'],'REVIEW_REQUIRED')
    def test_wrong_child_order_does_not_bind(self):
        algo,close=self.setup_exit(child=True);close['orderId']='999'
        result=self.run_job();self.assertEqual(result['items'][0]['reason'],'BOT_TP_EXIT_BINDING')
    def test_lost_tp_client_binding_is_rejected(self):
        algo,close=self.setup_exit();close['clientOrderId']='other'
        result=self.run_job();self.assertEqual(result['items'][0]['reason'],'BOT_TP_CLIENT_BINDING')
    def test_truncated_algo_history_blocks_resolution(self):
        self.setup_exit();original=self.reader.read.side_effect
        self.reader.read.side_effect=lambda op,**q: {'orders':[],'hasMore':True} if op=='get_capi_v3_allAlgoOrders' else original(op,**q)
        self.assertEqual(self.run_job()['items'][0]['reason'],'INCOMPLETE_ALGO_HISTORY')
    def test_user_supplied_manual_close_id_completes_missing_history(self):
        close=self.orders.pop();self.rows[2]=[];original=self.reader.read.side_effect
        self.reader.read.side_effect=lambda op,**q:copy.deepcopy(close) if op=='get_capi_v3_order' else original(op,**q)
        result=module.run(self.root,'u','c',reader=self.reader,refresh=self.refresh,symbol='ETH',order_ids=['3'])
        self.assertEqual(result['status'],'DONE',result);self.assertFalse(self.calls)
        self.assertEqual(result['items'][0]['state'],'CLOSED_EXTERNAL')
    def test_supplied_order_from_other_symbol_is_rejected(self):
        close=self.orders.pop();close['symbol']='BTCUSDT';original=self.reader.read.side_effect
        self.reader.read.side_effect=lambda op,**q:copy.deepcopy(close) if op=='get_capi_v3_order' else original(op,**q)
        result=module.run(self.root,'u','c',reader=self.reader,refresh=self.refresh,symbol='ETH',order_ids=['3'])
        self.assertEqual(result['items'][0]['reason'],'ORDER_SYMBOL_MISMATCH');self.assertFalse(self.calls)
    def test_supplied_id_cannot_overwrite_conflicting_history(self):
        close=copy.deepcopy(self.orders[1]);close['cumQuote']='999';original=self.reader.read.side_effect
        self.reader.read.side_effect=lambda op,**q:copy.deepcopy(close) if op=='get_capi_v3_order' else original(op,**q)
        result=module.run(self.root,'u','c',reader=self.reader,refresh=self.refresh,symbol='ETH',order_ids=['3'])
        self.assertEqual(result['items'][0]['reason'],'ORDER_OBSERVATION_CHANGED');self.assertFalse(self.calls)
    def test_detail_and_action_are_available_after_failure(self):
        self.orders.pop();result=self.run_job()
        text=module.diagnostics(self.root,'ETH')
        self.assertIn('Quantità registrata: 2',text);self.assertIn('chiusura trovati: 0',text)
        self.assertIn('/risolvi ETH ID_ORDINE',text)
        self.assertIn('/risolvi ETH',module.message(result))
        self.assertEqual(module.keyboard(result)['inline_keyboard'][0][0]['callback_data'],'livectl:resolve:ETHUSDT')
    def test_invalid_order_id_is_rejected_before_stopping(self):
        with self.assertRaises(ValueError):module.run(self.root,'u','c',symbol='ETH',order_ids=['../file'])
        module.control.stop.assert_not_called()
    def test_symbol_resolution_does_not_touch_other_trade(self):
        result=module.run(self.root,'u','c',reader=self.reader,refresh=self.refresh,symbol='BTC')
        self.assertEqual(result['items'],[]);self.assertFalse(self.calls)

class ResolveTelegramTests(unittest.TestCase):
    def update(self,text,user=1):return {'message':{'date':int(time.time()),'from':{'id':user},'chat':{'id':1},'text':text}}
    def test_resolve_arguments_and_authentication(self):
        from telegram_live_control import handle
        cfg={'telegram_chat_id':1}
        r=handle(self.update('/risolvi AAVE 123 456'),cfg)
        self.assertEqual(r['reconcileRequest'],{'user':'1','chat':'1','symbol':'AAVEUSDT','orderIds':['123','456']})
        self.assertIsNone(handle(self.update('/risolvi AAVE',user=2),cfg)['reply'])
        for text in ('/risolvi','/risolvi AAVE x','/risolvi AAVE 1 2 3 4 5 6'):
            self.assertNotIn('reconcileRequest',handle(self.update(text),cfg))
    def test_callback_resolution(self):
        from telegram_live_control import handle
        r=handle({'callback_query':{'data':'livectl:resolve:AAVEUSDT','from':{'id':1},'message':{'chat':{'id':1}}}}, {'telegram_chat_id':1})
        self.assertEqual(r['reconcileRequest']['symbol'],'AAVEUSDT')
    def test_blocks_command_is_read_only(self):
        from telegram_live_control import handle
        with tempfile.TemporaryDirectory() as tmp,patch('live_control.stop') as stop:
            r=handle(self.update('/blocchi AAVE'),{'telegram_chat_id':1},Path(tmp))
            self.assertNotIn('reconcileRequest',r);stop.assert_not_called()
    def test_background_worker_passes_explicit_resolution_target(self):
        import commands
        with patch.object(module,'run',return_value={'status':'DONE','items':[]}) as run,patch.object(commands,'api') as api:
            commands._run_reconciliation('DUMMY','1','1','AAVEUSDT',['123'])
            run.assert_called_once_with(commands.ROOT,'1','1',symbol='AAVEUSDT',order_ids=['123'])
            self.assertIn('reply_markup',api.call_args.args[2])

if __name__=='__main__':unittest.main()
