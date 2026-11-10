import copy,json,tempfile,unittest
from datetime import datetime,timezone,timedelta
from pathlib import Path
from unittest.mock import Mock,patch
from weex_execution_cycle import candidates,tick,exclusive,run
from weex_lifecycle import Lifecycle
from test_weex_lifecycle import Exchange,CFG,PLAN
import test_weex_lifecycle as lifecycle_fixtures
from weex_account_setup_audit import assess


class CycleTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.exchange=Exchange();self.cfg=copy.deepcopy(CFG)
        self.path=self.root/'weex_lifecycle.sqlite3'
        self.engine=Lifecycle(self.path,self.exchange,lambda:self.cfg)
        self.item=self.engine.prepare('cycle1',PLAN);self.tid=self.item['id']
    def context(self,item):return lifecycle_fixtures.LifecycleTests.ctx(self,item['symbol'])
    def test_future_authorized_fixture_full_cycle_across_ticks_and_restart(self):
        self.assertEqual(tick(self.engine,self.context,[self.tid])[0]['state'],'TP_PENDING')
        restarted=Lifecycle(self.path,self.exchange,lambda:self.cfg)
        self.assertEqual(tick(restarted,self.context,[])[0]['state'],'PROTECTED')
        self.exchange.positions=[];self.exchange.algos[0].update(algoStatus='FILLED',actualOrderId='3')
        self.assertEqual(tick(restarted,self.context,[])[0]['state'],'CLOSED')
        self.assertEqual(tick(restarted,self.context,[]),[])
        self.assertEqual(len(self.exchange.calls),2)
    def test_recovery_runs_without_current_market_signal(self):
        self.exchange.fail='entry';tick(self.engine,self.context,[self.tid])
        self.assertEqual(tick(self.engine,self.context,[])[0]['state'],'PROTECTED')
        self.assertEqual(sum(op=='post_capi_v3_order' for op,p in self.exchange.calls),1)
    def test_unknown_recovery_blocks_new_entry(self):
        with patch.object(self.exchange,'write',side_effect=TimeoutError()):tick(self.engine,self.context,[self.tid])
        plan=copy.deepcopy(PLAN);plan['orderPreview']['symbol']='BTCUSDT'
        other=self.engine.prepare('cycle2',plan)['id']
        result=tick(self.engine,self.context,[other])
        self.assertEqual(result[-1]['state'],'BLOCKED_BY_UNRESOLVED_LIFECYCLE')
        self.assertEqual(self.engine.writes(other),{})
    def test_partial_fill_recovery_stops_residual_then_tp(self):
        self.exchange.partial=True
        self.assertEqual(tick(self.engine,self.context,[self.tid])[0]['state'],'ENTRY_PENDING')
        self.assertEqual(tick(self.engine,self.context,[])[0]['state'],'TP_PENDING')
        self.assertEqual(tick(self.engine,self.context,[])[0]['state'],'PROTECTED')
        self.assertEqual(self.engine.get(self.tid)['owned']['quantity'],'0.01')
    def test_repeated_pretrade_ticks_never_write_or_poll_market(self):
        self.cfg['execution'].update(enabled=False,mode='PRETRADE')
        context=Mock(side_effect=AssertionError())
        for _ in range(2):self.assertEqual(tick(self.engine,context,[self.tid])[0]['state'],'STOP_BEFORE_SUBMISSION')
        context.assert_not_called();self.assertEqual(self.exchange.calls,[]);self.assertEqual(self.engine.writes(self.tid),{})
    def test_scheduled_entrypoint_is_readonly_even_if_config_is_toggled(self):
        (self.root/'weex_ai_risk_config.json').write_text(json.dumps(self.cfg),encoding='utf-8')
        scan={'checkedAt':datetime.now(timezone.utc).isoformat(),'mode':'READ_ONLY_PREVIEW','ordersSubmitted':False,
              'results':[{'marketSignal':'LONG','plan':{'status':'BLOCKED_PREVIEW'},'lifecycle':{'tradeId':self.tid}}]}
        (self.root/'weex_simple_bot_latest.json').write_text(json.dumps(scan),encoding='utf-8')
        with patch('weex_simple_bot.make_client') as client:
            result=run(self.root)
            self.assertEqual(result['status'],'CONFIG_UNSAFE')
            self.assertEqual(result['results'][0]['state'],'STOP_BEFORE_SUBMISSION')
            client.return_value.rest_api.execute_operation.assert_not_called()
        self.assertEqual(self.engine.writes(self.tid),{})
    def test_scheduled_recovery_cannot_send_missing_tp_even_when_config_live(self):
        def unknown(op,payload):
            if op=='post_capi_v3_placeTpSlOrder':raise TimeoutError()
            return Exchange.write(self.exchange,op,payload)
        with patch.object(self.exchange,'write',side_effect=unknown):tick(self.engine,self.context,[self.tid])
        (self.root/'weex_ai_risk_config.json').write_text(json.dumps(self.cfg),encoding='utf-8')
        gateway=Mock();gateway.read.side_effect=self.exchange.read
        with patch('weex_simple_bot.make_client'),patch('weex_execution_cycle.SDKGateway',return_value=gateway):
            result=run(self.root)
            self.assertEqual(result['recoveredCount'],1);gateway.write.assert_not_called()
    def test_exclusive_lock_blocks_parallel_cycle_and_releases(self):
        path=self.root/'test.lock'
        with exclusive(path):
            with self.assertRaisesRegex(RuntimeError,'CYCLE_ALREADY_RUNNING'):
                with exclusive(path):pass
        with exclusive(path):pass
    def test_stale_future_missing_and_duplicate_scans_never_admit_new_entries(self):
        now=datetime.now(timezone.utc)
        base={'checkedAt':now.isoformat(),'mode':'READ_ONLY_PREVIEW','ordersSubmitted':False,
              'results':[{'marketSignal':'LONG','plan':{'status':'BLOCKED_PREVIEW'},'lifecycle':{'tradeId':'x'}}]}
        self.assertEqual(candidates(base,now),(['x'],None))
        for report in ({},{**base,'checkedAt':(now-timedelta(hours=1)).isoformat()},
                       {**base,'checkedAt':(now+timedelta(seconds=2)).isoformat()},{**base,'results':base['results']*2}):
            self.assertEqual(candidates(report,now)[0],[])


class SetupAuditTests(unittest.TestCase):
    def base(self):
        return ([{'symbol':'ETHUSDT','maxLeverage':400,'contractType':'PERPETUAL','quoteAsset':'USDT'}],
                {'ETHUSDT'},[{'symbol':'ETHUSDT','marginType':'CROSSED','crossLeverage':'20'}],
                [{'symbol':'ETHUSDT','brackets':[{'notionalFloor':0,'notionalCap':100000,'initialLeverage':400}]}],5)
    def test_leverage_mismatch_is_reported_not_changed(self):
        args=self.base();result=assess(*args)[0]
        self.assertEqual(result['state'],'SETUP_REQUIRED');self.assertEqual(args[2][0]['crossLeverage'],'20')
    def test_config_and_tier_must_both_match(self):
        args=self.base();args[2][0]['crossLeverage']='400';self.assertTrue(assess(*args)[0]['matches'])
        args[3][0]['brackets'][0]['initialLeverage']=200
        self.assertEqual(assess(*args)[0]['state'],'PUBLIC_TIER_UNCONFIRMED')
    def test_bulk_omission_does_not_certify_default_settings(self):
        args=self.base();args[2].clear()
        self.assertEqual(assess(*args)[0]['state'],'ACCOUNT_CONFIG_MISSING')
    def test_duplicate_config_is_rejected(self):
        args=self.base();args[2].append(args[2][0].copy())
        with self.assertRaises(ValueError):assess(*args)


if __name__=='__main__':unittest.main()
