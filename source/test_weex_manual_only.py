import copy,json,tempfile,time,unittest
from contextlib import closing,ExitStack
from pathlib import Path
from unittest.mock import Mock,patch
import live_control as control
import weex_live_worker as worker
from weex_lifecycle import now
from weex_trading_modes import set_mode,get_mode,enqueue_manual,claim_next
from test_weex_native_trailing import TrailingExchange,signal
from test_weex_lifecycle import PLAN,CFG

class ManualOnlyWorkerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        set_mode(self.root,'manual_only','owner');control.state(self.root)
        with closing(control.connect(self.root)) as c,c:c.execute("UPDATE switch_v1 SET mode='RUNNING'")
        self.cfg=copy.deepcopy(CFG)
        # Offline fixture models a separately collateralized account.
        # Production cross-margin entry safety remains enforced independently.
        self.cfg['environment']='live_requested_not_enabled'
        self.cfg['risk']['marginModePreference']='isolated'
        self.cfg['strategySettings']['slMode']='off'
        self.cfg['execution']['allowOrdersWithoutStop']=True
        self.exchange=TrailingExchange()
        self.reader=Mock(root=self.root)
        self.reader.read.side_effect=self.exchange.read
        self.reader.account.side_effect=lambda:(copy.deepcopy(self.exchange.positions),[],copy.deepcopy(self.exchange.algos))
        self.reader.diagnostic_account.side_effect=self.reader.account.side_effect
        self.reader.excluded_demo_ids=[]
        outer=self
        class Gateway:
            def __init__(self,root,reader):self.root=root;self.reader=reader
            def read(self,op,**q):return outer.exchange.read(op,**q)
            def write(self,op,p):return outer.exchange.write(op,p)
        self.gateway=Gateway
        self.capture=Mock(side_effect=self.plan)
        for p in (patch.object(control,'configuration',side_effect=lambda root:(copy.deepcopy(self.cfg),'hash')),
                  patch.object(control,'build_errors',return_value=[]),
                  patch.object(worker,'candidates',side_effect=AssertionError('AUTOMATIC_SCAN_MUST_NOT_RUN')),
                  patch.object(worker,'capacity',return_value={'count':1,'symbols':[]})):
            p.start();self.addCleanup(p.stop)
    def plan(self,reader,symbol,cfg,*,manual_side=None,manual_request_id=None):
        self.assertIn(manual_side,('LONG','SHORT'))
        p=copy.deepcopy(PLAN);p['orderPreview'].update(positionSide=manual_side,side='BUY' if manual_side=='LONG' else 'SELL')
        p.update(entrySource='manual_telegram',liveAuthorizationScope=worker.SCOPE,beforePositions=[])
        if cfg['strategySettings'].get('tpMode')=='trailing':
            from weex_trailing import entry_policy
            p['exitPolicy']=entry_policy(signal(),p['targetNetProfitUSDT'])
        ctx={'observedAtMs':now(),'complete':True,'apiEnabled':True,'accountCanTrade':True,'hedgeMode':True,
         'depthUnitVerified':True,'liquidityPassed':True,'marketSignal':manual_side,'marketDataValid':True,
         'riskTierVerified':True,'availableBalance':'100','positions':[],'openOrders':[],'conditionalOrders':[],
         'symbolConfig':{'symbol':symbol,'marginType':self.exchange.margin,'crossLeverage':self.exchange.leverage},
         'referencePrice':'2500','exitFeeRate':'0.0008','maximumPermittedLeverage':'100'}
        return p,ctx,{}
    def run_worker(self,**kw):return worker.run(self.root,reader=self.reader,gateway_factory=self.gateway,capture_fn=self.capture,**kw)
    def test_periodic_cycle_waits_without_automatic_entry(self):
        result=self.run_worker()
        self.assertEqual(result['status'],'WAIT_MANUAL_REQUEST',result)
        self.capture.assert_not_called();self.assertFalse(self.exchange.calls)
    def test_manual_long_same_lifecycle_and_tp_with_automatic_capacity_full(self):
        req=enqueue_manual(self.root,'ETH','LONG','owner')
        result=self.run_worker(manual_only=True,manual_request_id=req['id'])
        self.assertEqual(result['status'],'MANUAL_PROTECTED',result)
        self.assertEqual(len([x for x in self.exchange.calls if x[0]=='post_capi_v3_order']),1)
        self.assertEqual(len([x for x in self.exchange.calls if x[0]=='post_capi_v3_placeTpSlOrder']),1)
        self.assertEqual(result['manualRequests'][0]['side'],'LONG')
    def test_scheduled_cycle_consumes_manual_short_but_never_falls_through(self):
        enqueue_manual(self.root,'ETH','SHORT','owner')
        result=self.run_worker()
        self.assertEqual(result['status'],'MANUAL_PROTECTED',result)
        self.assertEqual(self.exchange.order['side'],'SELL')
        self.assertEqual(self.exchange.algos[0]['positionSide'],'SHORT')
    def test_manual_trailing_uses_configured_exit_policy(self):
        self.cfg['strategySettings']['tpMode']='trailing';enqueue_manual(self.root,'ETH','LONG','owner')
        result=self.run_worker();self.assertEqual(result['status'],'MANUAL_PROTECTED',result)
        self.assertEqual(len(self.exchange.trailing),1)
        self.assertEqual(len([x for x in self.exchange.calls if x[0]=='post_capi_v3_algoOrder']),1)
    def test_restart_keeps_protection_and_no_duplicate_entry(self):
        enqueue_manual(self.root,'ETH','LONG','owner');self.run_worker();before=len(self.exchange.calls)
        result=self.run_worker();self.assertTrue(result['recoveryClear'],result)
        self.assertEqual(result['status'],'WAIT_MANUAL_REQUEST');self.assertEqual(len(self.exchange.calls),before)
    def test_stop_cancels_pending_without_entry(self):
        enqueue_manual(self.root,'ETH','LONG','owner');control.stop('owner','chat',self.root)
        result=self.run_worker();self.assertEqual(result['status'],'DISARMED_READY');self.assertFalse(self.exchange.calls)
        self.assertIsNone(claim_next(self.root))
    def test_balance_failure_does_not_open_or_fall_back_to_auto(self):
        original=self.plan
        def poor(*a,**kw):
            p,c,s=original(*a,**kw);c['availableBalance']='0';return p,c,s
        self.capture.side_effect=poor;enqueue_manual(self.root,'ETH','LONG','owner')
        result=self.run_worker();self.assertEqual(result['status'],'MANUAL_REJECTED',result)
        self.assertFalse(self.exchange.calls)
    def test_final_gateway_blocks_automatic_plan_even_when_called_directly(self):
        g=worker.Gateway(self.root,self.reader);g.current='trade';g.ctx={};g.engine=Mock()
        entry={'symbol':'ETHUSDT'}
        plan={'entry':entry,'liveAuthorizationScope':worker.SCOPE,'authorization':{'host':worker.HOST},
            'entrySource':'automatic','setupRequests':[{'operation':'margin','payload':{}},{'operation':'leverage','payload':{}}]}
        g.engine.get.return_value={'id':'trade','plan':plan,'owned':None}
        g.engine.writes.return_value={'ENTRY':{'state':'UNKNOWN','payload':entry}}
        with self.assertRaisesRegex(PermissionError,'AUTOMATIC_ENTRY_DISABLED'):g.validate('post_capi_v3_order',entry)
        g.engine.guard.assert_not_called()
        plan['entrySource']='manual_telegram';self.assertEqual(g.validate('post_capi_v3_order',entry)[0],'ENTRY')

class ManualOnlyTelegramTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        cfg=json.loads(Path(__file__).with_name('weex_ai_risk_config.json').read_text(encoding='utf-8'))
        (self.root/'weex_ai_risk_config.json').write_text(json.dumps(cfg))
        self.cfg={'telegram_chat_id':'7'}
    def msg(self,text):return {'message':{'date':int(time.time()),'text':text,'from':{'id':7},'chat':{'id':7}}}
    def test_menu_switch_stop_start_confirmation_then_manual_queue(self):
        from telegram_live_control import handle
        from telegram_ai_fullmenu import trading_mode_menu,trading_mode_text
        update={'callback_query':{'data':'tradingmode:set:manual_only','from':{'id':7},'message':{'chat':{'id':7}}}}
        with patch.object(control,'readiness',return_value=[]):
            result=handle(update,self.cfg,self.root);self.assertIn('Solo manuale',result['reply']['text'])
            self.assertEqual(get_mode(self.root)['mode'],'manual_only');self.assertEqual(control.state(self.root)['mode'],'STOPPED')
            blocked=handle(self.msg('ETH LONG'),self.cfg,self.root);self.assertNotIn('manualRequest',blocked)
            start=handle(self.msg('/live_start'),self.cfg,self.root)
            self.assertIn('Avvio Solo manuale',start['reply']['text']);self.assertNotIn('posizioni automatiche',start['reply']['text'])
            callback=start['reply']['reply_markup']['inline_keyboard'][0][0]['callback_data']
            confirmed=handle({'callback_query':{'data':callback,'from':{'id':7},'message':{'chat':{'id':7}}}},self.cfg,self.root)
            self.assertIn('Solo manuale LIVE attivo',confirmed['reply']['text'])
            queued=handle(self.msg('ETH SHORT'),self.cfg,self.root);self.assertEqual(queued['manualRequest']['side'],'SHORT')
            with patch('telegram_ai_fullmenu.get_mode',return_value={'mode':'manual_only'}):
                self.assertIn('Solo manuale',trading_mode_text())
                self.assertTrue(any(b['callback_data']=='tradingmode:set:manual_only' for row in trading_mode_menu()['inline_keyboard'] for b in row))
    def test_changing_mode_invalidates_old_confirmation_and_pending_request(self):
        from telegram_live_control import handle
        set_mode(self.root,'automatic_manual','owner')
        with patch.object(control,'readiness',return_value=[]):
            old=control.request_start('7','7',self.root)
            enqueue_manual(self.root,'ETH','LONG','owner')
            handle({'callback_query':{'data':'tradingmode:set:manual_only','from':{'id':7},'message':{'chat':{'id':7}}}},self.cfg,self.root)
            self.assertFalse(control.confirm_start(old['nonce'],'7','7',self.root)['started'])
            self.assertIsNone(claim_next(self.root))
    def test_manual_disabled_in_automatic_and_alerts_modes(self):
        for mode in ('automatic','alerts_only'):
            set_mode(self.root,mode,'owner')
            with self.assertRaises(PermissionError):enqueue_manual(self.root,'ETH','LONG','owner')

if __name__=='__main__':unittest.main()
