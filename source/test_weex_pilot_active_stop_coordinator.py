"""Coordinator integration test: protected active-stop close, no exchange writes."""
import json,shutil,unittest
from pathlib import Path
from unittest.mock import patch
from test_weex_pilot_active_stop_close_plan import ActiveStopSafePlan
import weex_pilot_live_close_coordinator as coordinator

class DummyReader:
 def __init__(self,root):pass
 def account(self):return DummyReader.observations

class CoordinatorActiveStop(unittest.TestCase):
 def setUp(self):
  self.fixture=ActiveStopSafePlan('test_active_stop_can_be_retained_before_exact_position_close')
  self.fixture.setUp()
  self.addCleanup(self.fixture.doCleanups)
  self.root=Path(self.fixture.tmp.name)
  shutil.copyfile(self.fixture.db,self.root/'weex_isolated_pilot.sqlite3')
  (self.root/'weex_live_1x_pilot_config.json').write_text(
    json.dumps({'executionEnabled':True,'liveOrderSubmissionAllowed':True}))
  DummyReader.observations=(self.fixture.position,[],self.fixture.stop)
 def test_coordinator_routes_to_exact_active_stop_without_cancellation(self):
  oid=str(self.fixture.order['orderId'])
  entryid=self.fixture.order['clientOrderId']
  def fake_query(url):
   if url=='/capi/v3/order?orderId='+oid:return self.fixture.order
   if url=='/capi/v3/userTrades?symbol=ETHUSDT&orderId='+oid+'&limit=100':
    return self.fixture.fills
   raise AssertionError('UNEXPECTED_READ')
  def fake_dispatch(db,pilot_id,*,ownership,observed_position,transport,main_mode):
   self.assertEqual(pilot_id,'P')
   self.assertTrue(ownership['owned'])
   self.assertEqual(ownership['positionId'],str(self.fixture.position[0]['id']))
   self.assertEqual(main_mode,'STOPPED')
   return {'state':'TEST_DISPATCH_NOT_CALLED','exchangeWrites':0}
  patches=[
   patch.object(coordinator.live_control,'state',return_value={'mode':'STOPPED'}),
   patch.object(coordinator.live_control,'build_errors',return_value=[]),
   patch.object(coordinator,'journals',return_value=[{'pilotId':'P','entryId':entryid,'side':'LONG','quantity':'0.002'}]),
   patch.object(coordinator,'baseline_load',return_value=self.fixture.baseline),
   patch.object(coordinator,'Reader',DummyReader),
   patch.object(coordinator,'history',return_value={
      'completeWithinRequestedBounds':True,
      'orders':[{'clientOrderId':entryid,'orderId':oid}]}),
   patch.object(coordinator,'query',side_effect=fake_query),
   patch.object(coordinator,'PilotEmergencyCloseSDK',return_value=object()),
   patch.object(coordinator,'dispatch',side_effect=fake_dispatch)]
  with patches[0],patches[1],patches[2],patches[3],patches[4],patches[5],patches[6],patches[7],patches[8]:
   result=coordinator.emergency_close_owned(self.root,pilot_id='P',approve=lambda x:True)
  self.assertEqual(result['exchangeWrites'],0)
 def test_mismatched_stop_is_blocked_before_dispatch(self):
  DummyReader.observations=(self.fixture.position,[],[{**self.fixture.stop[0],
       'actualOrderId':'wrong-entry'}])
  oid=str(self.fixture.order['orderId'])
  cid=self.fixture.order['clientOrderId']
  with patch.object(coordinator.live_control,'state',return_value={'mode':'STOPPED'}),patch.object(
       coordinator.live_control,'build_errors',return_value=[]),patch.object(
       coordinator,'journals',return_value=[{'pilotId':'P','entryId':cid,'side':'LONG','quantity':'0.002'}]),patch.object(
       coordinator,'baseline_load',return_value=self.fixture.baseline),patch.object(
       coordinator,'Reader',DummyReader),patch.object(
       coordinator,'history',return_value={'completeWithinRequestedBounds':True,
            'orders':[{'clientOrderId':cid,'orderId':oid}]}),patch.object(
       coordinator,'query',side_effect=lambda url:
         self.fixture.order if '/order?orderId=' in url else self.fixture.fills),patch.object(
       coordinator,'dispatch',side_effect=AssertionError('DISPATCH_NOT_ALLOWED')):
   with self.assertRaisesRegex(PermissionError,'EXIT_NOT_ATTESTED'):
    coordinator.emergency_close_owned(self.root,pilot_id='P',approve=lambda _:True)
if __name__=='__main__':unittest.main()
