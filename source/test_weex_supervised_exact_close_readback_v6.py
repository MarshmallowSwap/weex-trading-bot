"""Negative cases and positive closed+flat proof for read-only WEEX exit audit."""
import copy,unittest
from weex_supervised_exact_close_readback_v6 import classify,readback
E={'symbol':'ETHUSDT','positionSide':'LONG','quantity':'0.001','newClientOrderId':'wxentry_TEST'}
P={'symbol':'ETHUSDT','side':'SELL','positionSide':'LONG','quantity':'0.001','reduceOnly':True}
O={'orderId':'123456','symbol':'ETHUSDT','side':'SELL','positionSide':'LONG',
   'status':'FILLED','reduceOnly':True,'executedQty':'0.001'}
F=[{'id':'333','orderId':'123456','symbol':'ETHUSDT','side':'SELL',
    'positionSide':'LONG','qty':'0.001'}]
S=[{'clientAlgoId':'wxentry_TESTsl','algoId':'789','symbol':'ETHUSDT','side':'SELL',
    'positionSide':'LONG','reduceOnly':True,'algoStatus':'CANCELED','quantity':'0.001'}]
A={'positions':[],'regular':[],'conditional':[]}
def check(e=E,p=P,o=O,f=F,s=S,a=A,oid='123456'):
 return classify(e,p,o,f,s,a,close_order_id=oid)
class CloseVerifierTests(unittest.TestCase):
 def test_exact_proof_is_not_live_release(self):
  r=check()
  self.assertEqual(r['status'],'EXACT_CLOSE_AND_FLAT_VERIFIED')
  self.assertTrue(r['verifiedFlat'])
  self.assertFalse(r['releaseCertified'])
  self.assertFalse(r['safeToRetryClose'])
 def test_close_id_mismatch(self):
  self.assertFalse(check(oid='123457')['verifiedFlat'])
 def test_partial_fill_mismatch(self):
  self.assertFalse(check(o=dict(O,executedQty='0.0005'))['verifiedFlat'])
 def test_duplicate_fill_id(self):
  self.assertFalse(check(f=F+[dict(F[0])])['verifiedFlat'])
 def test_open_position_or_order_or_stop(self):
  for key in A:
   with self.subTest(key=key):
    a=dict(A);a[key]=[{'symbol':'ETHUSDT'}]
    self.assertEqual(check(a=a)['status'],'ACCOUNT_NOT_FLAT')
 def test_foreign_ain_manual_position_tp_not_a_close_target(self):
  a={'positions':[{'symbol':'AINUSDT','id':'901','side':'SHORT'}],
     'regular':[],
     'conditional':[{'symbol':'AINUSDT','algoId':'902','reduceOnly':True}]}
  self.assertTrue(check(a=a)['verifiedFlat'])
 def test_foreign_position_and_dangling_eth_order_fails(self):
  a={'positions':[{'symbol':'AINUSDT','id':'901'}],
     'regular':[{'symbol':'ETHUSDT','orderId':'999'}],
     'conditional':[]}
  self.assertFalse(check(a=a)['verifiedFlat'])
 def test_unknown_symbol_fails_closed(self):
  a={'positions':[{'id':'901'}], 'regular':[], 'conditional':[]}
  self.assertEqual(check(a=a)['status'],'ACCOUNT_SNAPSHOT_INVALID')
 def test_missing_or_active_stop(self):
  self.assertFalse(check(s=[])['verifiedFlat'])
  self.assertFalse(check(s=[dict(S[0],algoStatus='NEW')])['verifiedFlat'])
 def test_wrong_qty_or_order_kind(self):
  self.assertFalse(check(p=dict(P,quantity='0.01'))['verifiedFlat'])
  self.assertFalse(check(o=dict(O,reduceOnly=False))['verifiedFlat'])
 def test_missing_close_id_never_reads_exchange(self):
  self.assertEqual(readback(close_order_id=None)['status'],'EXACT_CLOSE_ORDER_ID_REQUIRED')
 def test_exact_close_client_id_recovery(self):
  from weex_supervised_exact_close_readback_v6 import resolve_close_order_id
  payload=dict(P,newClientOrderId='wxclose_TEST')
  hist=[{'clientOrderId':'wxclose_TEST','orderId':'123456',
         'symbol':'ETHUSDT','side':'SELL','positionSide':'LONG',
         'reduceOnly':True,'origQty':'0.001'}]
  self.assertEqual(resolve_close_order_id(hist,payload),'123456')
  self.assertIsNone(resolve_close_order_id(hist+hist,payload))
  self.assertIsNone(resolve_close_order_id([],payload))
  self.assertIsNone(resolve_close_order_id([dict(hist[0],reduceOnly=False)],payload))
  self.assertIsNone(resolve_close_order_id([dict(hist[0],origQty='0.01')],payload))
  self.assertIsNone(resolve_close_order_id([dict(hist[0],clientOrderId='another')],payload))
if __name__=='__main__':unittest.main()
