"""Integrated simulated SDK + single-use scoped grant + independent GET readback."""
import json,subprocess,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import requests
from weex_cross_1x_single_use_approval_20261109 import grant,consume,SingleUseApproval
from weex_cross_1x_close_sdk_adapter_20261109 import Cross1xCloseAdapter
from weex_cross_1x_supervised_executor_20261109 import dispatch,get_record
from weex_cross_1x_independent_close_readback_20261109 import check
from test_weex_cross_1x_emergency_readiness_20261109 import I,E,P,S

class FakeSession:
 simulation_only=True
 def __init__(self,loss=False):
  self.calls=0;self.loss=loss;self.payloads=[]
 def request(self,method,url,**kwargs):
  self.calls+=1
  assert method=='POST' and url=='https://api-contract.weex.com/capi/v3/closePositions'
  self.payloads.append(json.loads(kwargs['data']))
  if self.loss:raise TimeoutError('ACK_LOST_AFTER_FAKE_EXCHANGE_ACCEPT')
  r=requests.Response();r.status_code=200
  r._content=b'[{"positionId":201,"success":true,"successOrderId":401}]'
  r.headers['Content-Type']='application/json'
  return r
 def close(self):pass

class FakeReader:
 def __init__(self,*,bad=False):self.calls=[];self.bad=bad
 def read(self,op,**q):
  self.calls.append(op)
  if self.bad:raise RuntimeError('EXCHANGE_API_FAILURE')
  if op=='get_capi_v3_order':
   return {'orderId':'401','symbol':'ETHUSDT','positionSide':'LONG','side':'SELL',
     'status':'FILLED','reduceOnly':True,'executedQty':'0.002'}
  if op=='get_capi_v3_userTrades':
   return [{'id':'501','orderId':'401','symbol':'ETHUSDT',
      'side':'SELL','positionSide':'LONG','qty':'0.002'}]
  if op=='get_capi_v3_allAlgoOrders':
   return {'hasMore':False,'orders':[{'algoId':'301','algoStatus':'CANCELED'}]}
  raise AssertionError('UNEXPECTED_READ_'+op)
 def account(self):self.calls.append('account');return [],[],[]

class TestIntegrated(unittest.TestCase):
 def setUp(self):
  self.t=tempfile.TemporaryDirectory();self.addCleanup(self.t.cleanup)
  self.root=Path(self.t.name);self.db=self.root/'close.sqlite3'
  self.auth=self.root/'approval.sqlite3'
  self.scope={'pilotId':I['newClientOrderId'],'entryOrderId':'101',
    'positionId':'201','stopAlgoId':'301',
    'payload':{'symbol':'ETHUSDT','positionId':201}}
 def arm(self):return grant(self.auth,self.scope,approved_by_operator=True)
 def execute(self,session=None,approval=None):
  self.fake=session or FakeSession()
  adapter=Cross1xCloseAdapter(session_factory=lambda:self.fake)
  return dispatch(self.db,pilot_id=I['newClientOrderId'],intent=I,entry=E,
    positions=[P],regular_orders=[],conditional=[S],
    exchange_cross_leverage='1',
    approval=approval if approval is not None else SingleUseApproval(self.auth),
    transport=adapter,main_bot_stopped=True)
 def test_complete_simulated_weex_flow(self):
  self.arm()
  result=self.execute();self.assertEqual(result['state'],'ACK_RECEIVED_NEEDS_READBACK')
  self.assertEqual(self.fake.calls,1)
  self.assertEqual(self.fake.payloads,[{'symbol':'ETHUSDT','positionId':201}])
  proof=check(self.db,I['newClientOrderId'],reader=FakeReader())
  self.assertTrue(proof['verifiedFlat']);self.assertEqual(proof['status'],'CLOSED_VERIFIED')
  second=self.execute(FakeSession(),approval=lambda _:True)
  self.assertEqual(second['state'],'ALREADY_RESERVED_NO_RETRY')
 def test_no_grant_denies_transport(self):
  with self.assertRaises(PermissionError):self.execute()
  self.assertIsNone(get_record(self.db,I['newClientOrderId']))
 def test_scope_change_denied(self):
  self.arm()
  self.assertFalse(consume(self.auth,{**self.scope,'positionId':'202',
   'payload':{'symbol':'ETHUSDT','positionId':202}}))
  self.assertTrue(consume(self.auth,self.scope))
  self.assertFalse(consume(self.auth,self.scope))
 def test_grant_is_single_use_and_persistent(self):
  self.arm()
  self.assertTrue(SingleUseApproval(self.auth)(self.scope))
  code='from weex_cross_1x_single_use_approval_20261109 import consume;import json,sys;print(consume(sys.argv[1],json.loads(sys.argv[2])))'
  r=subprocess.run([sys.executable,'-c',code,str(self.auth),json.dumps(self.scope)],
      capture_output=True,text=True,timeout=10)
  self.assertEqual(r.returncode,0,r.stderr);self.assertIn('False',r.stdout)
 def test_fake_lost_ack_stays_unknown_no_retry(self):
  self.arm()
  lost=FakeSession(loss=True)
  result=self.execute(lost)
  self.assertEqual(result['state'],'OUTCOME_UNKNOWN')
  self.assertEqual(lost.calls,1)
  state=check(self.db,I['newClientOrderId'],reader=FakeReader())
  self.assertFalse(state['verifiedFlat'])
  self.assertEqual(state['reason'],'ACK_UNCERTAIN_NO_GUESS_NO_RESEND')
  r=self.execute(FakeSession(),approval=lambda _:True)
  self.assertEqual(r['state'],'ALREADY_RESERVED_NO_RETRY')
 def test_fake_readback_failure_does_not_certify(self):
  self.arm();self.execute()
  r=check(self.db,I['newClientOrderId'],reader=FakeReader(bad=True))
  self.assertFalse(r['verifiedFlat']);self.assertEqual(r['exchangeWrites'],0)
 def test_no_actual_network_session(self):
  with self.assertRaises(PermissionError):
   Cross1xCloseAdapter(session_factory=lambda:requests.Session(),mode='LIVE')
  with self.assertRaises(PermissionError):
   Cross1xCloseAdapter(session_factory=lambda:requests.Session(),credential_provider=lambda:{'api_key':'x'})
 def test_not_simulated_session_blocked(self):
  self.arm()
  adapter=Cross1xCloseAdapter(session_factory=lambda:requests.Session())
  r=dispatch(self.db,pilot_id=I['newClientOrderId'],intent=I,entry=E,
    positions=[P],regular_orders=[],conditional=[S],
    exchange_cross_leverage='1',approval=SingleUseApproval(self.auth),
    transport=adapter,main_bot_stopped=True)
  self.assertEqual(r['state'],'OUTCOME_UNKNOWN')
  self.assertEqual(adapter.send_count,0)
 def test_duplicate_scope_grant_refused(self):
  self.arm()
  with self.assertRaises(PermissionError):self.arm()
 def test_no_implicit_operator_grant(self):
  with self.assertRaises(PermissionError):grant(self.auth,self.scope)
 def test_expired_grant_refused(self):
  with self.assertRaises(PermissionError):grant(self.auth,self.scope,approved_by_operator=True,ttl_seconds=0)
if __name__=='__main__':unittest.main()
