import unittest
from weex_pilot_unified_lifecycle_readonly import check
P={'pilotId':'p1','side':'LONG','quantity':'0.002','entryId':'entry','closeId':'wxpilot_close_test','state':'PREPARED_NO_SEND'}
O={'clientOrderId':'entry','orderId':'EX-1','status':'FILLED','symbol':'ETHUSDT','positionSide':'LONG','side':'BUY'}
F=[{'id':'f1','orderId':'EX-1','qty':'0.002','symbol':'ETHUSDT','positionSide':'LONG','side':'BUY'}]
POS=[{'symbol':'ETHUSDT','side':'LONG','size':'0.002','marginType':'ISOLATED','manualOrMixed':False}]
def go(rows=None,positions=None,regular=None,algos=None,order=None,fills=None):
 return check([P] if rows is None else rows,POS if positions is None else positions,
              [] if regular is None else regular,[] if algos is None else algos,
              lambda cid:O if order is None else order,
              lambda s,oid:F if fills is None else fills)
class PilotLifecycle(unittest.TestCase):
 def test_empty_is_not_authorized(self):
  r=go(rows=[])
  self.assertEqual(r['pilots'],0)
  self.assertFalse(r['entryAuthorization']);self.assertFalse(r['exitAuthorization'])
 def test_known_entry_without_baseline_must_not_prepare_close(self):
  r=go();self.assertFalse(r['audits'][0]['closePrepared'])
  self.assertFalse(r['audits'][0]['canSend'])
 def test_exact_attested_entry_prepares_without_authorizing(self):
  entry={**O,'time':1100,'executedQty':'0.002'}
  fills=[{**F[0],'time':1250}]
  position=[{**POS[0],'id':'77','createdTime':1200}]
  baseline={'account':'CURRENT_WEEX','snapshotVerified':True,
            'observedAtMs':1000,'positions':[],'regularOrders':[],'conditionalOrders':[]}
  r=check([P],position,[],[],lambda _:entry,lambda s,o:fills,baseline)
  self.assertTrue(r['audits'][0]['closePrepared'],r)
  self.assertFalse(r['exitAuthorization']);self.assertFalse(r['audits'][0]['canSend'])
 def test_missing_entry_is_not_matched(self):
  r=go(order={})
  self.assertEqual(r['audits'][0]['state'],'ENTRY_NOT_OBSERVED')
 def test_manual_mixed_never_prepares_close(self):
  r=go(positions=[{**POS[0],'manualOrMixed':True}])
  self.assertFalse(r['audits'][0]['closePrepared'])
 def test_unknown_provenance_never_prepares_close(self):
  r=go(positions=[{k:v for k,v in POS[0].items() if k!='manualOrMixed'}])
  self.assertFalse(r['audits'][0]['closePrepared'])
 def test_extra_position_blocks(self):
  r=go(positions=POS+POS)
  self.assertFalse(r['audits'][0]['closePrepared'])
 def test_open_order_blocks(self):
  r=go(regular=[{'symbol':'ETHUSDT'}])
  self.assertFalse(r['audits'][0]['closePrepared'])
 def test_incomplete_fills_blocks(self):
  r=go(fills=[{**F[0],'qty':'0.001'}])
  self.assertFalse(r['audits'][0]['closePrepared'])
if __name__=='__main__':unittest.main()
