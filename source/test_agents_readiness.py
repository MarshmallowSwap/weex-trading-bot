import copy,json,sqlite3,tempfile,unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path
from unittest.mock import patch
import agent_health as health
import module_health
from weex_live_preflight import verify_after_submit

NOW=datetime(2026,10,23,1,tzinfo=timezone.utc)
STAMP=NOW.isoformat()
REPORTS={
 'weex_ai_risk_config.json':{'execution':{'enabled':False}},
 'universe_latest.json':{'scannedAt':STAMP,'count':132,'apiTradingSymbolsChecked':True},
 'market_agents_latest.json':{'asOf':STAMP,'liveTrading':False,'results':[
  {'symbol':'ETHUSDT','decision':'WAIT','marketSignal':'WAIT','trend':{'aligned':False},
   'momentum':{'confirmed':False},'realOrderBook':{'status':'OK','depthUnitVerified':False,'passed':False}}]},
 'weex_simple_bot_latest.json':{'checkedAt':STAMP,'mode':'READ_ONLY_PREVIEW','ordersSubmitted':False,
  'positionCount':1,'openOrderCount':0,'results':[{'symbol':'ETHUSDT','marketSignal':'WAIT'}]},
 'position_manager_integrated_latest.json':{'asOf':STAMP,'completeWithinBounds':True,'exchangeWrites':False,'positions':1},
 'weex_agent_orchestrator_latest.json':{'checkedAt':STAMP,'cycleStatus':'OK','mode':'SHADOW_ONLY','ordersSubmitted':False,'sourceMarketAt':STAMP}
}

class ReadinessTests(unittest.TestCase):
 def assess(self,reports=None,now=NOW):
  with patch.object(health,'load_report',side_effect=lambda n:(reports or REPORTS).get(n,{})):
   return health.assess_agents(now)
 def test_wait_is_healthy_analysis_but_unverified_units_block(self):
  result=self.assess()
  self.assertTrue(result['analysisReady'])
  self.assertEqual(result['modules']['liquidity']['state'],'BLOCKED_UNITS')
  self.assertFalse(result['pretradeReady']);self.assertFalse(result['liveReady'])
 def test_stale_reports_never_ready(self):
  self.assertFalse(self.assess(now=NOW+timedelta(hours=2))['analysisReady'])
 def test_future_reports_never_ready(self):
  self.assertFalse(self.assess(now=NOW-timedelta(minutes=1))['analysisReady'])
 def test_wrong_shadow_batch_not_ready(self):
  r=copy.deepcopy(REPORTS);r['weex_agent_orchestrator_latest.json']['sourceMarketAt']='old'
  self.assertEqual(self.assess(r)['modules']['orchestrator']['state'],'STALE_OR_DEGRADED')
 def test_missing_heartbeat_does_not_create_database(self):
  with tempfile.TemporaryDirectory() as folder:
   db=Path(folder)/'missing.sqlite3'
   with patch.object(health,'DB',db):self.assertEqual(health.assess(NOW)['status'],'ERROR')
   self.assertFalse(db.exists())
 def test_liquidity_telemetry_tracks_book_not_candle_proxy(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);db=root/'telemetry.db'
   (root/'market_agents_latest.json').write_text(json.dumps(REPORTS['market_agents_latest.json']),encoding='utf-8')
   with patch.object(module_health,'ROOT',root),patch.object(module_health,'DB',db):
    self.assertEqual(module_health.refresh()['liquidity_book'],1)
    self.assertEqual(module_health.state()['liquidity_book']['state'],'OBSERVED')


def evidence():
 return dict(client_order_id='wxpilot_test',
  ack={'success':True,'clientOrderId':'wxpilot_test','orderId':'1'},
  intent={'symbol':'ETHUSDT','side':'BUY','positionSide':'LONG','quantity':'0.002',
          'newClientOrderId':'wxpilot_test','tpTriggerPrice':'2500','TpWorkingType':'MARK_PRICE'},
  orders=[{'orderId':'1','clientOrderId':'wxpilot_test','symbol':'ETHUSDT','positionSide':'LONG',
           'side':'BUY','status':'FILLED','executedQty':'0.002'}],
  positions=[{'id':'123','symbol':'ETHUSDT','side':'LONG','size':'0.002'}],
  trades=[{'id':'9','orderId':'1','symbol':'ETHUSDT','positionSide':'LONG','side':'BUY','qty':'0.002'}],
  before_positions=[{'id':'99','symbol':'IOSTUSDT','side':'SHORT','size':'822500'}],
  expected_tp_id='42',snapshot_complete=True,snapshot_age_ms=100,
  tp_orders=[{'algoId':'42','symbol':'ETHUSDT','positionSide':'LONG','side':'SELL','orderType':'TAKE_PROFIT_MARKET',
              'algoStatus':'UNTRIGGERED','quantity':'0.002','triggerPrice':'2500','workingType':'MARK_PRICE','reduceOnly':True}])

class ReconciliationTests(unittest.TestCase):
 def test_real_schema_matches_without_entry_order_id(self):
  result=verify_after_submit(**evidence())
  self.assertEqual(result['state'],'OPEN_WITH_MATCHED_TP')
  self.assertEqual(result['positionId'],'123');self.assertFalse(result['canClose']);self.assertFalse(result['canSubmit'])
 def test_explicit_rejection_is_not_unknown_or_success(self):
  data=evidence();data['ack']={'success':False}
  self.assertEqual(verify_after_submit(**data)['state'],'ORDER_REJECTED')
 def test_partial_fill_does_not_pass(self):
  data=evidence();data['orders'][0].update(status='PARTIALLY_FILLED',executedQty='0.001')
  self.assertEqual(verify_after_submit(**data)['reason'],'ORDER_NOT_FULLY_FILLED')
 def test_missing_or_duplicate_fill_blocks(self):
  for fills in ([],evidence()['trades']*2):
   data=evidence();data['trades']=fills
   self.assertEqual(verify_after_submit(**data)['state'],'RECONCILIATION_REQUIRED')
 def test_mixed_manual_symbol_blocks(self):
  data=evidence();data['before_positions'].append({'symbol':'ETHUSDT','size':'0.001'})
  self.assertEqual(verify_after_submit(**data)['reason'],'PREEXISTING_SYMBOL_EXPOSURE')
 def test_mismatched_position_quantity_blocks(self):
  data=evidence();data['positions'][0]['size']='0.003'
  self.assertEqual(verify_after_submit(**data)['reason'],'POSITION_QUANTITY_MISMATCH')
 def test_tp_identity_cannot_be_inferred_from_price(self):
  data=evidence();data['expected_tp_id']=None
  self.assertEqual(verify_after_submit(**data)['reason'],'TP_IDENTITY_NOT_BOUND')
 def test_tp_wrong_status_size_type_source_and_reduction_block(self):
  for change in ({'algoStatus':'CANCELED'},{'quantity':'0.001'},{'orderType':'STOP_MARKET'},
                 {'workingType':'CONTRACT_PRICE'},{'reduceOnly':False},{'side':'BUY'}):
   data=evidence();data['tp_orders'][0].update(change)
   with self.subTest(change=change):self.assertEqual(verify_after_submit(**data)['state'],'TP_NOT_CONFIRMED')
 def test_stale_or_incomplete_snapshot_blocks(self):
  for update in ({'snapshot_complete':False},{'snapshot_age_ms':6000},{'snapshot_age_ms':float('nan')}):
   data=evidence();data.update(update)
   self.assertEqual(verify_after_submit(**data)['reason'],'INCOMPLETE_OR_STALE_SNAPSHOT')

if __name__=='__main__':unittest.main()
