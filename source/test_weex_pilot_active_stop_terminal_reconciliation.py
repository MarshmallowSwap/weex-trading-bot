"""No false PASS when a retained active stop lacks terminal exchange proof."""
import json,tempfile,unittest
from pathlib import Path
from contextlib import closing
from weex_isolated_pilot_offline_journal import reserve,connect
from weex_pilot_emergency_reconciliation import reconcile_active_stop_emergency
ROOT=Path(__file__).resolve().parent
class ActiveStopTerminalReadback(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
  self.db=Path(self.temp.name)/'pilot.db'
  reserve(self.db,pilot_id='P',side='LONG',quantity='0.002',stop_price='2000')
  evidence=json.loads((ROOT/'weex_sim_active_stop_close_independent_audit_20261109.json').read_text())
  self.stopid=evidence['stopAlgoId']
  self.oid=evidence['closeOrderId']
  self.hist=[{'algoId':self.stopid,'algoStatus':'CANCELED'}]
  self.order={'orderId':self.oid,'symbol':'ETHUSDT','positionSide':'LONG',
   'side':'SELL','status':'FILLED','executedQty':'0.002','reduceOnly':True}
  self.fills=[{'id':'offline_sim_fixture_fill','orderId':self.oid,'symbol':'ETHUSDT',
    'positionSide':'LONG','side':'SELL','qty':'0.002'}]
  with closing(connect(self.db)) as c:
   c.execute("UPDATE pilot_v1 SET state='ENTRY_RECONCILED_EXTERNALLY' WHERE pilot_id='P'")
   c.execute("CREATE TABLE pilot_emergency_dispatch_v1(pilot_id TEXT PRIMARY KEY,position_id TEXT,state TEXT,response TEXT)")
   c.execute("INSERT INTO pilot_emergency_dispatch_v1 VALUES(?,?,?,?)",
    ('P',evidence.get('positionId','123'),'ACK_RECEIVED_NEEDS_EXCHANGE_READBACK',json.dumps({'orderId':self.oid})))
   c.commit()
 def call(self,**kw):
  args=dict(stop_algo_id=self.stopid,stop_history=self.hist,order=self.order,
    fills=self.fills,positions=[],regular=[],conditional=[])
  args.update(kw)
  return reconcile_active_stop_emergency(self.db,'P',**args)
 def test_matching_terminal_stop_and_flat_account(self):
  result=self.call()
  self.assertTrue(result['confirmed'],result)
  with closing(connect(self.db)) as c:
   self.assertEqual(c.execute("SELECT state FROM pilot_v1 WHERE pilot_id='P'").fetchone()[0],
                    'CLOSED_VERIFIED_EXTERNALLY')
 def test_missing_terminal_stop_proof(self):
  self.assertFalse(self.call(stop_history=[])['confirmed'])
 def test_unrelated_stop_does_not_certify(self):
  self.assertFalse(self.call(stop_history=[{'algoId':'other','algoStatus':'CANCELED'}])['confirmed'])
 def test_active_stop_still_open_blocks(self):
  self.assertFalse(self.call(stop_history=[{'algoId':self.stopid,'algoStatus':'UNTRIGGERED'}])['confirmed'])
 def test_flat_with_residual_conditional_does_not_certify(self):
  self.assertFalse(self.call(conditional=[{'algoId':self.stopid}])['confirmed'])
 def test_missing_close_fill_blocks(self):
  self.assertFalse(self.call(fills=[])['confirmed'])
if __name__=='__main__':unittest.main()
