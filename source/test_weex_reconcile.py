import copy,json,tempfile,time,unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch,Mock
import weex_reconcile as module
from weex_lifecycle import Lifecycle,dump,now
from weex_close_proof import prove,flat_and_orphan
from weex_trailing import normalize
import live_control

def fixture(short=False,trailing=True):
    side='SHORT' if short else 'LONG';open_side='SELL' if short else 'BUY';close_side='BUY' if short else 'SELL'
    price='90' if short else '110';value='180' if short else '220';symbol='ETHUSDT'
    entry={'orderId':'1','clientOrderId':'wxentry_fixture','symbol':symbol,'side':open_side,'positionSide':side,
        'type':'MARKET','status':'FILLED','reduceOnly':False,'origQty':'2','executedQty':'2','avgPrice':'100','cumQuote':'200','time':1000}
    close={**entry,'orderId':'3','clientOrderId':'external','side':close_side,'reduceOnly':True,
        'avgPrice':price,'cumQuote':value,'time':2000}
    def fill(order):
        return {'id':'fill-'+order['orderId'],'orderId':order['orderId'],'symbol':symbol,'side':order['side'],
            'positionSide':side,'qty':'2','price':order['avgPrice'],'quoteQty':order['cumQuote'],
            'commission':'.2','commissionAsset':'USDT','time':order['time']+1}
    tp={'symbol':symbol,'clientAlgoId':'wxtp_fixture','quantity':'2','positionSide':side,'reduceOnly':True}
    if trailing:
        tp.update(type='TRAILING_MARKET',side=close_side,activatePrice='120',callbackRate='.003',workingType='MARK_PRICE')
        algo=normalize({**tp,'orderId':'2','clientOrderId':'wxtp_fixture','origQty':'2','status':'UNACTIVATED'})
    else:
        tp.update(planType='TAKE_PROFIT',triggerPrice='120',executePrice='0',triggerPriceType='MARK_PRICE',closePosition=False)
        algo={**tp,'algoId':'2','orderType':'TAKE_PROFIT_MARKET','side':close_side,'workingType':'MARK_PRICE','algoStatus':'UNTRIGGERED'}
    item={'id':'wxentry_fixture','symbol':symbol,'state':'REVIEW_REQUIRED','detail':{'reason':'EXPOSURE_CHANGED'},'created':900,'updated':2100,
        'plan':{'entry':entry,'beforePositions':[],'tpClientId':'wxtp_fixture','targetNetProfitUSDT':'10',
            'liveAuthorizationScope':'USER_ACTIVATED_LIVE_V1','authorization':{'host':module.HOST},
            'exitPolicy':{'mode':'trailing'} if trailing else {}},
        'owned':{'positionId':'position-1','quantity':'2','entryOrderId':'1','actualEntryCostUSDT':'200',
            'actualEntryFeesUSDT':'.2','tpRequest':tp}}
    return item,[entry,close],{'1':[fill(entry)],'3':[fill(close)]},[[],[],[algo]]

class ReconcileTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.item,self.orders,self.fills,self.rows=fixture();self.calls=[];self.fail_ack=False;self.keep_orphan=False
        self.engine=Lifecycle(self.root/'weex_user_live_lifecycle.sqlite3',None,lambda:{})
        self.insert_item()
        (self.root/'weex_credentials.json').write_text(dump({'api_key':'OFFLINE','secret_key':'OFFLINE','passphrase':'OFFLINE'}))
        self.state={'mode':'STOPPED','generation':1}
        self.patches=[patch.object(module.control,'state',side_effect=lambda *a:copy.deepcopy(self.state)),
            patch.object(module.control,'build_errors',return_value=[]),patch.object(module.control,'stop'),
            patch.object(module,'budget')]
        for p in self.patches:p.start();self.addCleanup(p.stop)
        module.budget.return_value.ready_at.return_value=0;module.budget.return_value.clock.return_value=1
        module.budget.return_value.used.return_value={'pauseUntil':0}
        self.reader=Mock();self.reader.account.side_effect=lambda:copy.deepcopy(self.rows)
        def read(op,**q):
            if op=='get_capi_v3_order_history':return copy.deepcopy(self.orders)
            if op=='get_capi_v3_allAlgoOrders':return {'orders':[],'hasMore':False}
            if op=='get_capi_v3_trailing_historyOrders':return []
            if op=='get_capi_v3_userTrades':return copy.deepcopy(self.fills[str(q['orderId'])])
            raise AssertionError(op)
        self.reader.read.side_effect=read
        self.refresh=Mock(return_value={'status':'DISARMED_READY','accountReadOK':True,'recoveryClear':True})
        outer=self
        class Network:
            def __enter__(self):return self
            def __exit__(self,*a):pass
            def request(self,method,url,**kw):
                outer.calls.append((method,url));outer.assertEqual((method,url),('DELETE',module.HOST+'/capi/v3/algoOrder?orderId=2'))
                if not outer.keep_orphan:outer.rows[2]=[]
                if outer.fail_ack:raise TimeoutError('lost ack')
                import requests
                r=requests.Response();r.status_code=200;r._content=b'{"success":true,"orderId":"2"}';r.headers={};return r
        p=patch('requests.Session',Network);p.start();self.addCleanup(p.stop)
    def insert_item(self):
        i=self.item
        with closing(self.engine.db()) as c,c:
            c.execute('insert or replace into trades_v1 values(?,?,?,?,?,?,?,?)',
                tuple(dump(i[k]) if k in ('plan','owned','detail') else i[k] for k in ('id','symbol','state','plan','owned','detail','created','updated')))
            c.execute('insert or replace into writes_v1 values(?,?,?,?,?,?,?)',
                (i['id'],'TP','post_capi_v3_algoOrder',dump(i['owned']['tpRequest']),'RESPONSE_RECEIVED',dump({'success':True,'orderId':'2'}),1))
    def run_job(self):return module.run(self.root,'owner','chat',reader=self.reader,refresh=self.refresh)
    def test_long_short_fixed_trailing_closes_and_cancels(self):
        for short,trailing in ((False,True),(True,False),(False,False),(True,True)):
            with self.subTest(short=short,trailing=trailing):
                self.item,self.orders,self.fills,self.rows=fixture(short,trailing);self.insert_item()
                with closing(self.engine.db()) as c,c:c.execute("delete from writes_v1 where kind='CANCEL_EXTERNAL_TP'")
                result=self.run_job();self.assertEqual(result['status'],'DONE',result)
                self.assertEqual(self.engine.get(self.item['id'])['state'],'CLOSED')
                self.assertEqual(self.engine.get(self.item['id'])['detail']['realizedNetBeforeFundingUSDT'],'19.6')
                self.assertTrue(result['items'][0]['orphanRemoved'])
        self.assertEqual(len(self.calls),4)
    def test_repeat_does_not_cancel_again(self):
        self.run_job();self.run_job();self.assertEqual(len(self.calls),1)
    def test_lost_ack_uses_readback(self):
        self.fail_ack=True;result=self.run_job();self.assertEqual(result['status'],'DONE')
        self.assertEqual(self.engine.writes(self.item['id'])['CANCEL_EXTERNAL_TP']['state'],'UNKNOWN')
        self.run_job();self.assertEqual(len(self.calls),1)
    def test_uncertain_cancel_still_open_never_retries(self):
        self.fail_ack=True;self.keep_orphan=True
        self.refresh.return_value={'status':'BLOCKED_RECOVERY','accountReadOK':True,'recoveryClear':False}
        self.run_job();self.run_job();self.assertEqual(len(self.calls),1)
        self.assertNotEqual(self.engine.get(self.item['id'])['state'],'CLOSED')
    def test_open_position_preserved(self):
        self.rows[0]=[{'symbol':'ETHUSDT','size':'2'}]
        result=self.run_job();self.assertEqual(result['items'][0]['state'],'POSITION_OPEN');self.assertFalse(self.calls)
        self.reader.read.assert_not_called()
    def test_changed_tp_refused(self):
        self.rows[2][0]['quantity']='1';self.run_job();self.assertFalse(self.calls)
        self.assertNotEqual(self.engine.get(self.item['id'])['state'],'CLOSED')
    def test_other_pending_order_refused(self):
        self.rows[1]=[{'symbol':'ETHUSDT','orderId':'other'}];self.run_job();self.assertFalse(self.calls)
    def test_wrong_ack_id_refused(self):
        self.rows[2][0]['algoId']='wrong';self.run_job();self.assertFalse(self.calls)
    def test_incomplete_fills_not_marked_closed(self):
        self.fills['3']=[];self.run_job();self.assertFalse(self.calls)
        self.assertEqual(self.engine.get(self.item['id'])['state'],'REVIEW_REQUIRED')
    def test_position_reappears_at_dispatch_not_cancelled(self):
        n=[0]
        def account():
            n[0]+=1
            rows=copy.deepcopy(self.rows)
            if n[0]>=3:rows[0]=[{'symbol':'ETHUSDT','size':'1'}]
            return rows
        self.reader.account.side_effect=account;self.run_job();self.assertFalse(self.calls)
        self.assertNotEqual(self.engine.get(self.item['id'])['state'],'CLOSED')
    def test_control_changed_aborts_without_cancel(self):
        def change(op,**q):self.state['generation']=2;return copy.deepcopy(self.orders)
        self.reader.read.side_effect=change
        self.assertEqual(self.run_job()['status'],'ERROR');self.assertFalse(self.calls)
    def test_busy_job_preserves_state(self):
        from weex_execution_cycle import exclusive
        with exclusive(self.root/'weex_reconcile.lock'):result=self.run_job()
        self.assertEqual(result['status'],'BUSY');module.control.stop.assert_not_called()
    def test_no_orphan_updates_ledger_without_network_write(self):
        self.rows[2]=[];self.run_job();self.assertFalse(self.calls)
        self.assertEqual(self.engine.get(self.item['id'])['state'],'CLOSED')
    def test_direct_gateway_rejects_unscoped_write(self):
        r=module.Reconciler(self.root,self.reader,self.state,Mock());r.current=self.item;r.proof={'proof':True}
        with self.assertRaises(PermissionError):r.write('post_capi_v3_order',{})
    def test_budget_wait_obeys_quota_then_resumes(self):
        progress=Mock();r=module.Reconciler(self.root,self.reader,self.state,progress)
        module.budget.return_value.ready_at.side_effect=[4,0]
        with patch.object(module.time,'sleep') as sleep:r.wait_budget(100)
        progress.assert_called_once_with('WAIT_API',waitSeconds=3);sleep.assert_called_once()
    def test_control_stop_during_wait_aborts(self):
        r=module.Reconciler(self.root,self.reader,self.state,Mock())
        module.budget.return_value.ready_at.return_value=4
        with patch.object(module.time,'sleep',side_effect=lambda _:self.state.update(generation=2)):
            with self.assertRaisesRegex(ValueError,'CONTROL_CHANGED'):r.wait_budget(100)
    def test_refresh_cannot_dispatch_or_create_unknown_writes(self):
        with patch('weex_lifecycle.Lifecycle.reconcile',side_effect=AssertionError('MUST_NOT_RUN')):
            result=module.run(self.root,'u','c',reader=self.reader)
        self.assertEqual(result['status'],'DONE',result)
        self.assertEqual(set(self.engine.writes(self.item['id'])),{'TP','CANCEL_EXTERNAL_TP'})
    def test_open_unprotected_position_refresh_does_not_reserve_tp(self):
        self.rows[0]=[{'symbol':'ETHUSDT','size':'2'}];self.rows[2]=[]
        with patch('weex_lifecycle.Lifecycle.reconcile',side_effect=AssertionError('MUST_NOT_RUN')):
            result=module.run(self.root,'u','c',reader=self.reader)
        self.assertEqual(result['status'],'REVIEW_REQUIRED')
        self.assertFalse(self.calls);self.assertEqual(set(self.engine.writes(self.item['id'])),{'TP'})

class ProofTests(unittest.TestCase):
    def test_extra_entry_rejected(self):
        i,orders,fills,rows=fixture();extra={**orders[0],'orderId':'4','time':1500};orders.append(extra)
        with self.assertRaises(ValueError):prove(i,orders,fills)
    def test_nonfinite_and_duplicate_fill_rejected(self):
        for mutation in ('nan','duplicate','wrong-side','wrong-quote'):
            i,orders,fills,rows=fixture();f=fills['3'][0]
            if mutation=='nan':f['commission']='NaN'
            elif mutation=='duplicate':fills['3'].append(copy.deepcopy(f))
            elif mutation=='wrong-side':f['side']='BUY'
            else:f['quoteQty']='1'
            with self.assertRaises(ValueError):prove(i,orders,fills)

class TelegramTests(unittest.TestCase):
    def update(self,user='7',stamp=None):return {'update_id':1,'message':{'message_id':1,'date':int(time.time()) if stamp is None else stamp,
        'from':{'id':user},'chat':{'id':'7'},'text':'/riconcilia'}}
    def test_authenticated_and_fresh_only(self):
        from telegram_live_control import handle,COMMANDS
        cfg={'telegram_chat_id':'7'}
        self.assertIn('reconcileRequest',handle(self.update(),cfg))
        self.assertIsNone(handle(self.update(user='8'),cfg)['reply'])
        self.assertNotIn('reconcileRequest',handle(self.update(stamp=1),cfg))
        self.assertIn('riconcilia',[c['command'] for c in COMMANDS])
    def test_callback_and_menu(self):
        from telegram_live_control import handle
        from telegram_button_menu import recovery
        self.assertTrue(any(b['callback_data']=='livectl:reconcile' for row in recovery()['inline_keyboard'] for b in row))
        update={'callback_query':{'data':'livectl:reconcile','from':{'id':'7'},'message':{'chat':{'id':'7'}}}}
        self.assertIn('reconcileRequest',handle(update,{'telegram_chat_id':'7'}))
    def test_active_reconciliation_blocks_start(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(live_control,'build_errors',return_value=[]):
            root=Path(tmp);module.save_status(root,{'status':'WAIT_API','checkedAt':live_control.timestamp()})
            self.assertIn('RICONCILIAZIONE_IN_CORSO',live_control.readiness(root))
    def test_result_message_distinguishes_open_and_closed(self):
        text=module.message({'status':'DONE','items':[{'symbol':'ETHUSDT','state':'CLOSED_EXTERNAL','orphanRemoved':True},
            {'symbol':'BTCUSDT','state':'POSITION_OPEN'}]})
        self.assertIn('TP residuo rimosso',text);self.assertIn('posizione ancora aperta',text);self.assertIn('/live_start',text)
    def test_actual_polling_dispatches_background_reconciliation_and_reports(self):
        import commands
        from contextlib import ExitStack
        class EndLoop(Exception):pass
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);tg=root/'tg.json';tg.write_text(json.dumps({'telegram_bot_token':'DUMMY','telegram_chat_id':'7'}))
            sent=[];connections=[];original=commands.sqlite3.connect
            def connect(*a,**kw):c=original(*a,**kw);connections.append(c);return c
            def api(token,method,args):
                if method=='getUpdates':return [self.update()]
                if method=='sendMessage':sent.append(args)
                return True
            with ExitStack() as stack:
                for obj,name,value in ((commands,'ROOT',root),(commands,'DB',root/'commands.sqlite3'),(commands,'TG',tg)):
                    stack.enter_context(patch.object(obj,name,value))
                stack.enter_context(patch.object(commands.sqlite3,'connect',side_effect=connect))
                stack.enter_context(patch.object(commands,'api',side_effect=api))
                stack.enter_context(patch.object(commands.time,'sleep',side_effect=EndLoop))
                thread=stack.enter_context(patch.object(commands.threading,'Thread'))
                with self.assertRaises(EndLoop):commands.main()
                self.assertEqual(thread.call_args.kwargs['target'],commands._run_reconciliation)
                self.assertEqual(thread.call_args.kwargs['args'],('DUMMY','7','7'))
                thread.return_value.start.assert_called_once()
                with patch.object(module,'run',return_value={'status':'DONE','items':[]}) as job:
                    commands._run_reconciliation('DUMMY','7','7')
                job.assert_called_once_with(root,'7','7')
                self.assertTrue(any('/live_start' in m['text'] for m in sent))
            for c in connections:c.close()

if __name__=='__main__':unittest.main()
