"""Offline test for distinct one-shot permission on production Lifecycle durable UNKNOWN."""
import copy,json,sqlite3,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
from weex_supervised_crash_executor_v2 import CLIENT_ID,SIGNAL_ID
from weex_supervised_one_shot_permission_v4 import authorize_once
from weex_supervised_entry_permit_v5 import check_and_consume,DispatchDenied
from weex_lifecycle import Lifecycle
from test_weex_supervised_lifecycle_stop_v3 import ProductionScopedPilot
from test_weex_lifecycle import Exchange,CFG,PLAN

class PermitIntegration(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.root=Path(self.tmp.name);self.permit=self.root/'permit.db'
  self.cfg={'risk':{'minimumLeverage':100},'execution':{'enabled':False,'mode':'PRETRADE'}}
  (self.root/'weex_ai_risk_config.json').write_text(json.dumps(self.cfg))
  self.plan=copy.deepcopy(PLAN)
  self.plan.update(entrySource='supervised_crash_pilot',pilotReferencePrice='2500')
  self.plan['orderPreview'].update(quantity='0.001',slTriggerPrice='2492.50',SlWorkingType='MARK_PRICE')
  self.engine=Lifecycle(self.root/'weex_user_live_lifecycle.sqlite3',Exchange(),lambda:CFG)
  item=self.engine.prepare(SIGNAL_ID,self.plan)
  self.assertEqual(item['id'],CLIENT_ID)
  self.payload=item['plan']['entry']
  con=sqlite3.connect(self.root/'weex_user_live_lifecycle.sqlite3')
  con.execute('INSERT INTO writes_v1 VALUES(?,?,?,?,?,?,?)',(CLIENT_ID,'ENTRY',
    'post_capi_v3_order',json.dumps(self.payload,sort_keys=True),'UNKNOWN',None,int(time.time()*1000)))
  con.commit();con.close()
  context={'mainMode':'STOPPED','productionIntegrity':True,'accountFlat':True,
   'accountLeverage':'100','atomicStopVerified':True,'closePathValidated':True,
   'independentSupervisorReady':True,'apiBudgetReady':True,'observedAtMs':int(time.time()*1000)}
  authorize_once(self.permit,self.payload,approval=True,context=context)
  self.patched=[
   patch('live_control.state',return_value={'mode':'STOPPED'}),
   patch('live_control.build_errors',return_value=[])]
  for p in self.patched:p.start();self.addCleanup(p.stop)
 def consume(self):return check_and_consume(root=self.root,permit_db=self.permit,payload=self.payload)
 def test_permit_consumed_once_and_never_repeat(self):
  self.assertEqual(self.consume()['status'],'CONSUMED_BEFORE_NETWORK')
  with self.assertRaisesRegex(DispatchDenied,'ALREADY_CONSUMED'):self.consume()
  with __import__("contextlib").closing(sqlite3.connect(self.permit)) as c:
   self.assertEqual(c.execute('SELECT status FROM permit').fetchone()[0],'DISPATCH_CONSUMED')
 def test_prod_running_rejected(self):
  with patch('live_control.state',return_value={'mode':'RUNNING'}):
   with self.assertRaisesRegex(DispatchDenied,'PRODUCTION_NOT_STOPPED'):self.consume()
 def test_wrong_payload_rejected(self):
  bad=dict(self.payload,slTriggerPrice='2490.00')
  with self.assertRaisesRegex(DispatchDenied,'JOURNAL_PAYLOAD_MISMATCH'):check_and_consume(root=self.root,permit_db=self.permit,payload=bad)
 def test_journal_unknown_mandatory(self):
  c=sqlite3.connect(self.root/'weex_user_live_lifecycle.sqlite3')
  c.execute("UPDATE writes_v1 SET state='RESPONSE_RECEIVED'")
  c.commit();c.close()
  with self.assertRaisesRegex(Exception,'NOT_UNKNOWN_PRE_ACK_WORKER_INTENT'):self.consume()
 def test_expired_token_rejected(self):
  c=sqlite3.connect(self.permit);c.execute('UPDATE permit SET created=?',(time.time()-300,));c.commit();c.close()
  with self.assertRaisesRegex(DispatchDenied,'EXPIRED'):self.consume()
 def test_wrong_minimum_leverage_rejected(self):
  self.cfg['risk']['minimumLeverage']=50
  (self.root/'weex_ai_risk_config.json').write_text(json.dumps(self.cfg))
  with self.assertRaisesRegex(DispatchDenied,'NOT_PRETRADE_100X'):self.consume()
if __name__=='__main__':unittest.main()
