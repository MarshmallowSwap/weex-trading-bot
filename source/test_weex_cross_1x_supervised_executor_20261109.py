import os,sqlite3,subprocess,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from weex_cross_1x_supervised_executor_20261109 import dispatch,reconcile,get_record
from test_weex_cross_1x_emergency_readiness_20261109 import I,E,P,S

class Transport:
 def __init__(self,loss=False):self.calls=0;self.loss=loss
 def __call__(self,op,p):
  self.calls+=1
  if self.loss:raise TimeoutError('ACK_LOST')
  return {'success':True,'orderId':'401','positionId':'201'}

class Supervised(unittest.TestCase):
 def setUp(self):
  t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup)
  self.db=Path(t.name)/'close.sqlite3'
  self.tx=Transport()
 def submit(self,**kw):
  p={'db':self.db,'pilot_id':I['newClientOrderId'],'intent':I,'entry':E,
     'positions':[P],'regular_orders':[],'conditional':[S],
     'exchange_cross_leverage':'1','approval':lambda _:True,
     'transport':self.tx,'main_bot_stopped':True}
  p.update(kw)
  return dispatch(**p)
 def test_only_one_close(self):
  self.assertEqual(self.submit()['state'],'ACK_RECEIVED_NEEDS_READBACK')
  self.assertEqual(self.submit()['state'],'ALREADY_RESERVED_NO_RETRY')
  self.assertEqual(self.tx.calls,1)
 def test_no_approval_no_reservation(self):
  with self.assertRaises(PermissionError):self.submit(approval=lambda _:False)
  self.assertIsNone(get_record(self.db,I['newClientOrderId']))
  self.assertEqual(self.tx.calls,0)
 def test_no_real_adapter_automatically_constructed(self):
  with self.assertRaises(PermissionError):self.submit(transport=None)
  self.assertEqual(self.tx.calls,0)
 def test_wrong_margin(self):
  with self.assertRaises(PermissionError):self.submit(positions=[{**P,'marginType':'ISOLATED'}])
  self.assertEqual(self.tx.calls,0)
 def test_no_native_stop(self):
  with self.assertRaises(PermissionError):self.submit(conditional=[])
  self.assertEqual(self.tx.calls,0)
 def test_bot_running(self):
  with self.assertRaises(PermissionError):self.submit(main_bot_stopped=False)
  self.assertEqual(self.tx.calls,0)
 def test_exact_pilot_id(self):
  with self.assertRaises(PermissionError):self.submit(pilot_id='other')
  self.assertEqual(self.tx.calls,0)
 def test_ack_lost_no_retry(self):
  self.tx=Transport(loss=True)
  self.assertEqual(self.submit()['state'],'OUTCOME_UNKNOWN')
  self.assertEqual(self.submit()['state'],'ALREADY_RESERVED_NO_RETRY')
  self.assertEqual(self.tx.calls,1)
  self.assertEqual(reconcile(self.db,pilot_id=I['newClientOrderId'],
    order={},fills=[],positions=[],regular_orders=[],conditional=[],
    terminal_stop_history=[])['state'],'OUTCOME_UNKNOWN_NO_ACK_NO_RETRY')
 def test_reopen_fresh_process_journal(self):
  self.assertEqual(self.submit()['state'],'ACK_RECEIVED_NEEDS_READBACK')
  code='from weex_cross_1x_supervised_executor_20261109 import get_record;import sys;print(get_record(sys.argv[1],sys.argv[2])["status"])'
  r=subprocess.run([sys.executable,'-c',code,str(self.db),I['newClientOrderId']],
    capture_output=True,text=True,timeout=10)
  self.assertEqual(r.returncode,0,r.stderr)
  self.assertIn('ACK_RECEIVED_NEEDS_READBACK',r.stdout)
 def test_wrong_close_response_remains_unknown(self):
  self.tx=lambda a,b:{'success':True,'orderId':'401','positionId':'909'}
  self.assertEqual(self.submit()['state'],'OUTCOME_UNKNOWN')
 def test_reconcile_complete(self):
  self.submit()
  order={'orderId':'401','symbol':'ETHUSDT','positionSide':'LONG','side':'SELL',
    'status':'FILLED','reduceOnly':True,'executedQty':'0.002'}
  fills=[{'id':'501','orderId':'401','symbol':'ETHUSDT','side':'SELL',
    'positionSide':'LONG','qty':'0.002'}]
  params={'db':self.db,'pilot_id':I['newClientOrderId'],'order':order,'fills':fills,
    'positions':[],'regular_orders':[],'conditional':[],
    'terminal_stop_history':[{'algoId':'301','algoStatus':'CANCELED'}]}
  self.assertEqual(reconcile(**params)['state'],'CLOSED_VERIFIED')
  self.assertEqual(reconcile(**params)['state'],'ALREADY_CLOSED_VERIFIED')
 def test_reconcile_stop_not_terminal(self):
  self.submit()
  self.assertFalse(reconcile(self.db,pilot_id=I['newClientOrderId'],
    order={'orderId':'401','symbol':'ETHUSDT','status':'FILLED'},
    fills=[],positions=[],regular_orders=[],conditional=[],
    terminal_stop_history=[{'algoId':'301','algoStatus':'NEW'}])['verifiedFlat'])
 def test_crash_after_fake_transport_accepts(self):
  code='''import os,sys
from weex_cross_1x_supervised_executor_20261109 import dispatch
from test_weex_cross_1x_emergency_readiness_20261109 import I,E,P,S
def send(op,p):
 open(sys.argv[2],'w').write('SIM_ACCEPTED')
 os._exit(73)
dispatch(db=sys.argv[1],pilot_id=I['newClientOrderId'],intent=I,entry=E,
 positions=[P],regular_orders=[],conditional=[S],exchange_cross_leverage='1',
 approval=lambda _:True,transport=send,main_bot_stopped=True)
'''
  marker=self.db.with_suffix('.fake')
  p=subprocess.run([sys.executable,'-c',code,str(self.db),str(marker)],
     capture_output=True,text=True,timeout=10)
  self.assertEqual(p.returncode,73,p.stderr)
  self.assertTrue(marker.exists())
  self.assertEqual(get_record(self.db,I['newClientOrderId'])['status'],'OUTCOME_UNKNOWN')
  self.assertEqual(self.submit()['state'],'ALREADY_RESERVED_NO_RETRY')
  self.assertEqual(self.tx.calls,0)
 def test_refuses_second_pilot_same_position(self):
  self.submit()
  other={**I,'newClientOrderId':'wxpilot_other'}
  second_entry={**E,'clientOrderId':'wxpilot_other'}
  stop={**S,'clientAlgoId':'wxpilot_othersl'}
  result=self.submit(pilot_id='wxpilot_other',intent=other,entry=second_entry,conditional=[stop])
  self.assertEqual(result['state'],'OTHER_RESERVATION_NO_RETRY')
  self.assertEqual(self.tx.calls,1)
if __name__=='__main__':unittest.main()
