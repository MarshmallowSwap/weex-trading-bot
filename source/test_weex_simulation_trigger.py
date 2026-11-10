import json,socket,tempfile,unittest
from datetime import datetime,timezone
from pathlib import Path
from unittest.mock import Mock,patch
import weex_simulation_trigger_trial as trial
import weex_simulation_soak as soak
import market_agents

class TriggerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        p=patch.object(trial.c.base,'FILE',Path(self.temp.name)/'journal.json');p.start();self.addCleanup(p.stop)
        self.state={'tradeId':'test','records':{},'deadlineAt':datetime.fromtimestamp(100,timezone.utc).isoformat(),
                    'protectedObserved':True}
        self.engine=Mock()
    def test_deadline_does_not_extend_or_submit_more(self):
        sleeper=Mock()
        trial.monitor(self.state,self.engine,{'state':'PROTECTED'},clock=lambda:101,sleep=sleeper)
        self.assertEqual(self.state['monitorStopReason'],'DEADLINE_REACHED')
        self.engine.reconcile.assert_not_called();sleeper.assert_not_called()
    def test_natural_closure_records_proof_and_stops(self):
        self.engine.reconcile.return_value={'state':'CLOSED','detail':{'exitOrderId':'123'}}
        trial.monitor(self.state,self.engine,{'state':'PROTECTED'},clock=lambda:90,sleep=Mock())
        self.assertEqual(self.state['naturalCloseLifecycle']['exitOrderId'],'123')
        self.assertEqual(self.engine.reconcile.call_count,1)
    def test_unresolved_reconciliation_is_bounded(self):
        result={'state':'REVIEW_REQUIRED','detail':{'reason':'TRANSIENT'}}
        self.engine.reconcile.return_value=result
        trial.monitor(self.state,self.engine,result,clock=lambda:90,sleep=Mock())
        self.assertEqual(self.engine.reconcile.call_count,3)
        self.assertEqual(self.state['monitorStopReason'],'RECONCILIATION_UNRESOLVED')
    def test_completed_trial_cannot_reopen(self):
        trial.c.base.FILE.write_text(json.dumps({'host':trial.c.SIM,'cycleScope':trial.SCOPE,'status':'CLOSED_VERIFIED'}))
        with patch.object(trial,'bind',return_value=Path(self.temp.name)),patch.object(trial.c,'engine_for') as factory:
            trial.execute()
        factory.assert_not_called()
    def test_rejected_preflight_does_not_wait(self):
        trial.monitor(self.state,self.engine,{'state':'PREFLIGHT_BLOCKED'},clock=lambda:90,sleep=Mock())
        self.engine.reconcile.assert_not_called()

class CandleTests(unittest.TestCase):
    def rows(self):
        return [[i*300000,'100','102','99','101','10',(i+1)*300000,'1010'] for i in range(85)]
    def test_only_completed_unique_contiguous_candles(self):
        rows=soak.closed_candles(self.rows(),'5m',85*300000)
        self.assertEqual(len(rows),84)
    def test_stale_duplicate_gap_nan_and_bad_ohlc_blocked(self):
        for kind in ('stale','duplicate','gap','nan','ohlc'):
            rows=self.rows();now=85*300000
            if kind=='stale':now+=1000000
            if kind=='duplicate':rows.append(rows[5])
            if kind=='gap':rows.pop(20)
            if kind=='nan':rows[20][4]='NaN'
            if kind=='ohlc':rows[20][4]='200'
            with self.subTest(kind=kind),self.assertRaises(ValueError):soak.closed_candles(rows,'5m',now)
    def test_agents_use_injected_simulation_reader_only(self):
        reader=Mock(return_value=self.rows())
        with patch.object(market_agents,'candles',side_effect=AssertionError('PRODUCTION_FORBIDDEN')):
            result=market_agents.analyze('BTCUSDT',candle_reader=reader)
        self.assertEqual(reader.call_count,3);self.assertFalse(result['orderPermitted'])
        self.assertEqual(set(result['timeframes']),{'5m','15m','1h'})

if __name__=='__main__':
    with patch.object(socket.socket,'connect',side_effect=AssertionError('NETWORK_DISABLED')):
        unittest.main(verbosity=2)
