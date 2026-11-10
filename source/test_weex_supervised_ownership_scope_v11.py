"""Offline ownership isolation regressions: never dispatch a network request."""
import unittest
from weex_supervised_ownership_scope_v11 import split_exact_symbol,OwnershipScopeBlocked
from weex_supervised_reduce_only_close_plan_v4 import compose,ClosePlanBlocked
from weex_supervised_crash_executor_v2 import CLIENT_ID
P={'symbol':'ETHUSDT','id':'100','side':'LONG','size':'0.001'}
S={'symbol':'ETHUSDT','algoId':'200','side':'SELL','reduceOnly':True}
M={'symbol':'AINUSDT','id':'901','side':'SHORT','size':'13200'}
TP={'symbol':'AINUSDT','algoId':'902','side':'BUY','reduceOnly':True}
PROOF={'status':'VERIFIED_PROTECTED_NEED_EXACT_CLOSE','clientOrderId':CLIENT_ID,
       'symbol':'ETHUSDT','quantity':'0.001','positionId':'100','stopAlgoId':'200'}
CFG=[{'symbol':'ETHUSDT','marginType':'CROSSED','crossLeverage':'100'}]
def plan(p,o,a):
 return compose(proof=PROOF,positions=p,regular_orders=o,conditional_orders=a,settings=CFG)
class ScopeTests(unittest.TestCase):
 def test_foreign_manual_position_and_tp_cannot_be_selected(self):
  s=split_exact_symbol([M,P],[],[TP,S])
  self.assertEqual(s['targetPositions'],[P])
  self.assertEqual(s['targetConditional'],[S])
  self.assertEqual(s['foreignPositions'],[M])
  self.assertFalse(s['entryAllowed'])
  result=plan([M,P],[],[TP,S])
  self.assertEqual(result['referencePositionId'],'100')
  self.assertEqual(result['referenceStopAlgoId'],'200')
  self.assertEqual(result['payload']['symbol'],'ETHUSDT')
  self.assertTrue(result['payload']['reduceOnly'])
  self.assertEqual(result['networkRequests'],0)
 def test_ordering_does_not_change_target(self):
  self.assertEqual(plan([P,M],[],[S,TP])['referencePositionId'],'100')
 def test_foreign_regular_order_not_our_close(self):
  extra={'symbol':'AINUSDT','orderId':'999'}
  self.assertEqual(plan([M,P],[extra],[TP,S])['referencePositionId'],'100')
 def test_unverified_target_position_does_not_select_foreign(self):
  with self.assertRaises(ClosePlanBlocked):plan([M],[],[TP,S])
 def test_second_target_position_or_stop_blocks(self):
  for p,o,a in (([M,P,dict(P,id='111')],[],[S,TP]),
                ([M,P],[],[S,TP,dict(S,algoId='222')]),
                ([M,P],[{'symbol':'ETHUSDT','orderId':'333'}],[S,TP])):
   with self.subTest(p=p,o=o,a=a):
    with self.assertRaises(ClosePlanBlocked):plan(p,o,a)
 def test_ambiguous_or_missing_symbol_fails_closed(self):
  for rows in (([dict(M,symbol='')],[],[]),([dict(P,symbol=None)],[],[]),
               ([],[{'orderId':'123'}],[])):
   with self.assertRaises(OwnershipScopeBlocked):split_exact_symbol(*rows)
if __name__=='__main__':unittest.main()
