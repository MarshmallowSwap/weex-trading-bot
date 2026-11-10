"""Safety tests for CROSS 1x live-close bridge, no real exchange sends."""
import json,sqlite3,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from weex_cross_1x_live_close_transport_20261109 import SupervisedCrossLiveClose
from weex_cross_1x_operator_telegram_20261109 import AUTH
from weex_cross_1x_single_use_approval_20261109 import fingerprint,grant,consume
from weex_cross_1x_supervised_executor_20261109 import db_connect
from test_weex_cross_1x_emergency_readiness_20261109 import I,E,P,S
from test_weex_cross_1x_transport_authorization_readback_20261109 import FakeSession
from weex_pilot_emergency_close_sdk import OP

SCOPE={'pilotId':'wxpilot_test_01','entryOrderId':'101','positionId':'201',
 'stopAlgoId':'301','payload':{'symbol':'ETHUSDT','positionId':201}}
class LiveBridge(unittest.TestCase):
 def setUp(self):
  t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup)
  self.root=Path(t.name)
  self.mode=patch('live_control.state',return_value={'mode':'STOPPED'});self.mode.start();self.addCleanup(self.mode.stop)
  self.integrity=patch('live_control.build_errors',return_value=[]);self.integrity.start();self.addCleanup(self.integrity.stop)
  self.scope=patch('weex_cross_1x_live_close_transport_20261109.current_scope',return_value=SCOPE)
  self.scope.start();self.addCleanup(self.scope.stop)
  (self.root/'weex_live_1x_pilot_config.json').write_text(json.dumps({
   'exchange':'WEEX','marginMode':'CROSS','leverage':1,'maxNewOrders':1,
   'executionEnabled':False,'requireExplicitTestOrderApproval':True,
   'supervisedEmergencyCloseAllowed':False}))
  (self.root/'weex_credentials.json').write_text(json.dumps({
   'api_key':'DUMMY','secret_key':'DUMMY','passphrase':'DUMMY'}))
 def adapter(self,mode='DRY_RUN',session=None):
  self.fake=session or FakeSession()
  return SupervisedCrossLiveClose(self.root,pilot_id=SCOPE['pilotId'],mode=mode,
    session_factory=lambda:self.fake)
 def prepare(self):
  with db_connect(self.root/'weex_cross_1x_supervised_close.sqlite3') as c:
   c.execute('BEGIN IMMEDIATE')
   c.execute('''INSERT INTO supervised_cross_close_v1
    (pilot_id,position_id,entry_order_id,stop_algo_id,payload,expected_qty,status,created_at)
    VALUES(?,?,?,?,?,?,?,?)''',
    (SCOPE['pilotId'],'201','101','301',json.dumps(SCOPE['payload']),
      '0.002','OUTCOME_UNKNOWN','2026-11-09T00:00:00+00:00'))
   c.commit()
  grant(self.root/AUTH,SCOPE,approved_by_operator=True)
  self.assertTrue(consume(self.root/AUTH,SCOPE))
 def test_without_reservation_denied(self):
  x=self.adapter()
  with self.assertRaises(PermissionError):x(OP,SCOPE['payload'])
  self.assertEqual(self.fake.calls,0)
 def test_with_reservation_but_no_grant_denied(self):
  with db_connect(self.root/'weex_cross_1x_supervised_close.sqlite3') as c:
   c.execute('BEGIN IMMEDIATE')
   c.execute('''INSERT INTO supervised_cross_close_v1
    (pilot_id,position_id,entry_order_id,stop_algo_id,payload,expected_qty,status,created_at)
    VALUES(?,?,?,?,?,?,?,?)''',
    (SCOPE['pilotId'],'201','101','301',json.dumps(SCOPE['payload']),'0.002','OUTCOME_UNKNOWN','now'))
   c.commit()
  x=self.adapter()
  with self.assertRaises(PermissionError):x(OP,SCOPE['payload'])
  self.assertEqual(self.fake.calls,0)
 def test_approved_dry_run_exact_once(self):
  self.prepare();x=self.adapter()
  result=x(OP,SCOPE['payload'])
  self.assertEqual(result['orderId'],'401')
  self.assertEqual(self.fake.calls,1)
  with self.assertRaises(PermissionError):x(OP,SCOPE['payload'])
  self.assertEqual(self.fake.calls,1)
 def test_expired_consumed_grant_cannot_send(self):
  self.prepare()
  from contextlib import closing
  with closing(sqlite3.connect(str(self.root/AUTH))) as c:
   c.execute("UPDATE cross_close_authorization_v1 SET expires_at='2020-01-01T00:00:00+00:00'")
   c.commit()
  x=self.adapter()
  with self.assertRaisesRegex(PermissionError,'EXPIRED'):x(OP,SCOPE['payload'])
  self.assertEqual(self.fake.calls,0)
 def test_live_requires_separate_switch(self):
  self.prepare();x=self.adapter(mode='LIVE')
  with self.assertRaisesRegex(PermissionError,'NOT_ARMED'):x(OP,SCOPE['payload'])
  self.assertEqual(self.fake.calls,0)
 def test_running_bot_blocks(self):
  self.prepare();x=self.adapter()
  with patch('live_control.state',return_value={'mode':'RUNNING'}):
   with self.assertRaises(PermissionError):x(OP,SCOPE['payload'])
  self.assertEqual(self.fake.calls,0)
 def test_changed_scope_denied(self):
  self.prepare();x=self.adapter()
  with patch('weex_cross_1x_live_close_transport_20261109.current_scope',
       return_value={**SCOPE,'entryOrderId':'102'}):
   with self.assertRaises(PermissionError):x(OP,SCOPE['payload'])
  self.assertEqual(self.fake.calls,0)
 def test_non_exact_payload_denied(self):
  self.prepare();x=self.adapter()
  with self.assertRaises(PermissionError):x(OP,{'symbol':'BTCUSDT','positionId':201})
  self.assertEqual(self.fake.calls,0)
 def test_ack_lost_does_not_retry(self):
  self.prepare();lost=FakeSession(loss=True);x=self.adapter(session=lost)
  with self.assertRaises(Exception):x(OP,SCOPE['payload'])
  with self.assertRaises(PermissionError):x(OP,SCOPE['payload'])
  self.assertEqual(lost.calls,1)
 def test_live_branch_sdk_exact_one_post_with_fully_fake_session(self):
  self.prepare()
  cfg=json.loads((self.root/'weex_live_1x_pilot_config.json').read_text())
  cfg['supervisedEmergencyCloseAllowed']=True
  (self.root/'weex_live_1x_pilot_config.json').write_text(json.dumps(cfg))
  x=self.adapter(mode='LIVE')
  from contextlib import nullcontext
  class Budget:
   def reserve(self,*args):return True
  with patch('weex_api_budget.budget',return_value=Budget()),patch('weex_api_budget.recovery',return_value=nullcontext()):
   result=x(OP,SCOPE['payload'])
  self.assertEqual(result['orderId'],'401')
  self.assertEqual(self.fake.calls,1)
  self.assertEqual(self.fake.payloads,[SCOPE['payload']])
  with self.assertRaises(PermissionError):x(OP,SCOPE['payload'])
  self.assertEqual(self.fake.calls,1)
 def test_stale_config_refuses_even_with_grant(self):
  self.prepare()
  cfg=json.loads((self.root/'weex_live_1x_pilot_config.json').read_text())
  cfg['marginMode']='ISOLATED';cfg['supervisedEmergencyCloseAllowed']=True
  (self.root/'weex_live_1x_pilot_config.json').write_text(json.dumps(cfg))
  x=self.adapter(mode='LIVE')
  with self.assertRaises(PermissionError):x(OP,SCOPE['payload'])
  self.assertEqual(self.fake.calls,0)
if __name__=='__main__':unittest.main()
