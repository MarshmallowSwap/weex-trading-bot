"""Offline regression: exact attached stop may remain active during close
preparation only with independently bound parent, fill, position, baseline.
The test uses past authenticated demo shapes with a synthetic test journal.
"""
import json,tempfile,unittest
from copy import deepcopy
from pathlib import Path
from contextlib import closing
from weex_isolated_pilot_offline_journal import reserve,connect
from weex_pilot_attach_atomic_stop import attach
from weex_pilot_active_stop_close_plan import assess
ROOT=Path(__file__).resolve().parent
class ActiveStopSafePlan(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory()
  self.addCleanup(self.tmp.cleanup)
  self.db=Path(self.tmp.name)/'pilot.sqlite3'
  src=json.loads((ROOT/'weex_sim_eth_trial_readback_latest.json').read_text())
  self.order=deepcopy(src['get_capi_v3_order'])
  self.position=deepcopy(src['get_capi_v3_account_position_allPosition'])
  self.stop=deepcopy(src['get_capi_v3_openAlgoOrders'])
  self.fills=deepcopy(src['get_capi_v3_userTrades'])
  self.assertEqual(len(self.position),1)
  self.assertEqual(len(self.stop),1)
  price=str(self.stop[0]['triggerPrice'])
  reserve(self.db,pilot_id='P',side='LONG',quantity='0.002',stop_price=price)
  attach(self.db,'P',stop=price,reference_price='2200')
  with closing(connect(self.db)) as c:
   p=json.loads(c.execute("SELECT proposals FROM pilot_v1 WHERE pilot_id='P'").fetchone()[0])
   p['entry']['newClientOrderId']=self.order['clientOrderId']
   c.execute("UPDATE pilot_v1 SET state='ENTRY_RECONCILED_EXTERNALLY',entry_id=?,proposals=? WHERE pilot_id='P'",
      (self.order['clientOrderId'],json.dumps(p)))
   c.commit()
  base_time=min(int(self.order['time']),int(self.position[0]['createdTime']),
       *(int(f['time']) for f in self.fills))-1
  self.baseline={'snapshotVerified':True,'account':'CURRENT_WEEX',
   'observedAtMs':base_time,'positions':[],'regularOrders':[],'conditionalOrders':[]}
 def plan(self,**modifications):
  values={'baseline':self.baseline,'positions':self.position,'regular_orders':[],
   'conditional_orders':self.stop,'entry_order':self.order,'entry_fills':self.fills}
  values.update(modifications)
  return assess(self.db,'P',**values)
 def test_active_stop_can_be_retained_before_exact_position_close(self):
  result=self.plan()
  self.assertTrue(result['prepared'],result)
  self.assertFalse(result['canSend'])
  self.assertFalse(result['stopCancellationRequired'])
  self.assertEqual(str(result['payload']['positionId']),str(self.position[0]['id']))
  self.assertEqual(result['attachedStopAlgoId'],str(self.stop[0]['algoId']))
 def test_wrong_stop_parent_is_rejected(self):
  stop=deepcopy(self.stop);stop[0]['actualOrderId']='not-parent'
  self.assertFalse(self.plan(conditional_orders=stop)['prepared'])
 def test_wrong_stop_client_binding_is_rejected(self):
  stop=deepcopy(self.stop);stop[0]['clientAlgoId']='manual'
  self.assertFalse(self.plan(conditional_orders=stop)['prepared'])
 def test_multiple_stops_rejected(self):
  self.assertFalse(self.plan(conditional_orders=self.stop+self.stop)['prepared'])
 def test_wrong_position_quantity_rejected(self):
  position=deepcopy(self.position);position[0]['size']='0.003'
  self.assertFalse(self.plan(positions=position)['prepared'])
 def test_entry_fill_mismatch_rejected(self):
  fills=deepcopy(self.fills);fills[0]['qty']='0.003'
  self.assertFalse(self.plan(entry_fills=fills)['prepared'])
 def test_unprotected_position_not_admitted_to_protected_path(self):
  self.assertFalse(self.plan(conditional_orders=[])['prepared'])
 def test_preexisting_exit_mutex_blocks(self):
  with closing(connect(self.db)) as c:
   c.execute('CREATE TABLE pilot_exit_mutex_v1(pilot_id TEXT PRIMARY KEY,method TEXT,state TEXT)')
   c.execute("INSERT INTO pilot_exit_mutex_v1 VALUES('P','position_id','CLAIMED_UNKNOWN')")
   c.commit()
  self.assertFalse(self.plan()['prepared'])
if __name__=='__main__':unittest.main()
