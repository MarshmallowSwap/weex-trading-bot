"""Offline-only one-shot safety policy tests."""
import copy,tempfile,time,unittest,sqlite3
from pathlib import Path
from weex_supervised_one_shot_permission_v4 import authorize_once,Denied,CLIENT_ID
class OneShot(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.db=Path(self.tmp.name)/'permit.db'
  self.p={'symbol':'ETHUSDT','side':'BUY','positionSide':'LONG','type':'MARKET',
    'quantity':'0.001','newClientOrderId':CLIENT_ID,
    'slTriggerPrice':'2110.00','SlWorkingType':'MARK_PRICE'}
  self.context={'mainMode':'STOPPED','productionIntegrity':True,'accountFlat':True,
    'accountLeverage':'100','atomicStopVerified':True,'closePathValidated':True,
    'independentSupervisorReady':True,'apiBudgetReady':True,
    'observedAtMs':int(time.time()*1000)}
 def call(self,approval=True):return authorize_once(self.db,self.p,approval=approval,context=self.context)
 def test_reserve_once_durable_and_never_dispatches(self):
  r=self.call()
  self.assertFalse(r['dispatchAllowed'])
  self.assertFalse(r['productionReleaseBypassed'])
  self.assertEqual(r['exchangeWrites'],0)
  with self.assertRaisesRegex(Denied,'ALREADY_CONSUMED'):self.call()
  with __import__("contextlib").closing(sqlite3.connect(self.db)) as c:
   self.assertEqual(c.execute('SELECT status FROM permit').fetchone()[0],'RESERVED_NO_RETRY')
 def test_no_external_approval(self):
  with self.assertRaisesRegex(Denied,'EXPLICIT_APPROVAL'):self.call(False)
 def test_missing_attached_stop(self):
  self.p.pop('slTriggerPrice')
  with self.assertRaisesRegex(Denied,'ENTRY_FIELDS'):self.call()
 def test_wrong_client_id(self):
  self.p['newClientOrderId']='wxentry_other'
  with self.assertRaisesRegex(Denied,'ONE_SHOT_SCOPE'):self.call()
 def test_wrong_quantity(self):
  self.p['quantity']='0.002'
  with self.assertRaisesRegex(Denied,'ONE_SHOT_SCOPE'):self.call()
 def test_missing_supervisor(self):
  self.context['independentSupervisorReady']=False
  with self.assertRaisesRegex(Denied,'GATES_NOT_ALL_PASSED'):self.call()
 def test_close_path_unverified(self):
  self.context['closePathValidated']=False
  with self.assertRaisesRegex(Denied,'GATES_NOT_ALL_PASSED'):self.call()
 def test_bot_must_remain_stopped(self):
  self.context['mainMode']='RUNNING'
  with self.assertRaisesRegex(Denied,'GATES_NOT_ALL_PASSED'):self.call()
 def test_account_leverage_mismatch(self):
  self.context['accountLeverage']='50'
  with self.assertRaisesRegex(Denied,'GATES_NOT_ALL_PASSED'):self.call()
 def test_stale_readback(self):
  self.context['observedAtMs']-=60000
  with self.assertRaisesRegex(Denied,'STALE_PRE_EXECUTION'):self.call()
 def test_missing_api_headroom(self):
  self.context['apiBudgetReady']=False
  with self.assertRaisesRegex(Denied,'GATES_NOT_ALL_PASSED'):self.call()
if __name__=='__main__':unittest.main()
