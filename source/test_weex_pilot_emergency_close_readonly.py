import unittest
from weex_pilot_emergency_close_readonly import evaluate

P=[{'pilotId':'pilot-a','side':'LONG','quantity':'0.002','closeId':'pilot-close'}]
ORDER={'clientOrderId':'pilot-close','orderId':'X-123','symbol':'ETHUSDT',
       'positionSide':'LONG','side':'SELL','reduceOnly':True,
       'status':'FILLED','origQty':'0.002','executedQty':'0.002'}
FILLS=[{'id':'f1','orderId':'X-123','symbol':'ETHUSDT',
        'positionSide':'LONG','side':'SELL','qty':'0.002'}]
class EmergencyProof(unittest.TestCase):
 def test_no_pilot_never_certified(self):
  r=evaluate([],[],lambda _:None,lambda s,o:[])
  self.assertFalse(r['allClosuresObservedUnattested'])
  self.assertFalse(r['liveCloseCertified'])
 def test_realistic_observations_are_still_unattested(self):
  r=evaluate(P,[],lambda cid:ORDER,lambda s,oid:FILLS)
  self.assertTrue(r['allClosuresObservedUnattested'])
  self.assertFalse(r['liveCloseCertified'])
  self.assertFalse(r['canSend'])
 def test_missing_order(self):
  r=evaluate(P,[],lambda cid:None,lambda s,oid:[])
  self.assertEqual(r['closures'][0]['reason'],'EXACT_CLIENT_ORDER_NOT_FOUND')
 def test_position_still_open(self):
  position=[{'symbol':'ETHUSDT','positionSide':'LONG','size':'0.002'}]
  r=evaluate(P,position,lambda cid:ORDER,lambda s,oid:FILLS)
  self.assertEqual(r['closures'][0]['reason'],'POSITION_STILL_OPEN')
 def test_order_is_not_reduce_only(self):
  r=evaluate(P,[],lambda cid:{**ORDER,'reduceOnly':False},lambda s,oid:FILLS)
  self.assertEqual(r['closures'][0]['reason'],'CLOSE_ORDER_NOT_EXACT')
 def test_partial_fill(self):
  r=evaluate(P,[],lambda cid:ORDER,lambda s,oid:[{**FILLS[0],'qty':'0.001'}])
  self.assertEqual(r['closures'][0]['reason'],'INCOMPLETE_FILLS')
if __name__=='__main__':unittest.main()
