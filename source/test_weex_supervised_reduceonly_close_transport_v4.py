"""Offline safety/one-shot tests for exact MARKET reduceOnly close transport."""
import json,sqlite3,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from weex_supervised_reduceonly_close_transport_v4 import (
 OnlyReduceClose,reserve,CloseDenied,send_once,OP,STATE)

CLOSE={'symbol':'ETHUSDT','side':'SELL','positionSide':'LONG','type':'MARKET',
 'quantity':'0.001','newClientOrderId':'wxclose_123456789012345678901234','reduceOnly':True}

class FakeResp:
 status_code=200
 headers={}
class ExactCloseTests(unittest.TestCase):
 def test_post_can_only_be_exact_reduce_only_payload(self):
  session=Mock()
  with patch('weex_supervised_reduceonly_close_transport_v4.budget_request',return_value=FakeResp()) as send:
   tr=OnlyReduceClose(CLOSE,session=session)
   reply=tr.request('POST','https://api-contract.weex.com/capi/v3/order',data=json.dumps(CLOSE))
   self.assertEqual(reply.status_code,200)
   self.assertEqual(tr.calls,1)
   send.assert_called_once()
   with self.assertRaisesRegex(CloseDenied,'REPEATED'):tr.request('POST','https://api-contract.weex.com/capi/v3/order',data=json.dumps(CLOSE))
 def test_wrong_endpoint_never_sends(self):
  tr=OnlyReduceClose(CLOSE,session=Mock())
  with patch('weex_supervised_reduceonly_close_transport_v4.budget_request',side_effect=AssertionError('NO_NETWORK')):
   with self.assertRaisesRegex(CloseDenied,'UNSCOPED'):tr.request('POST','https://api-contract.weex.com/capi/v3/closePositions',data=json.dumps(CLOSE))
  self.assertEqual(tr.calls,0)
 def test_mismatched_payload_never_sends(self):
  tr=OnlyReduceClose(CLOSE,session=Mock())
  with patch('weex_supervised_reduceonly_close_transport_v4.budget_request',side_effect=AssertionError('NO_NETWORK')):
   with self.assertRaisesRegex(CloseDenied,'UNSCOPED'):tr.request('POST','https://api-contract.weex.com/capi/v3/order',
    data=json.dumps(dict(CLOSE,quantity='0.002')))
  self.assertEqual(tr.calls,0)
 def test_not_reduce_only_fails_before_network(self):
  bad=dict(CLOSE,reduceOnly=False);tr=OnlyReduceClose(bad,session=Mock())
  with patch('weex_supervised_reduceonly_close_transport_v4.budget_request',side_effect=AssertionError('NO_NETWORK')):
   with self.assertRaisesRegex(CloseDenied,'NOT_A_REDUCE_ONLY'):tr.request('POST','https://api-contract.weex.com/capi/v3/order',data=json.dumps(bad))
 def test_durable_close_only_once(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)
   reserve(p,'wxentry_test',CLOSE)
   with self.assertRaisesRegex(CloseDenied,'NEVER_RESEND'):reserve(p,'wxentry_test',CLOSE)
   con=sqlite3.connect(p/STATE)
   try:
    self.assertEqual(con.execute('SELECT status FROM intents').fetchone()[0],'OUTCOME_UNKNOWN')
   finally:con.close()
 def test_no_external_approval_no_network(self):
  with tempfile.TemporaryDirectory() as d:
   with self.assertRaisesRegex(CloseDenied,'EXTERNAL_CLOSE_APPROVAL_REQUIRED'):
    send_once('wxentry_test',root=Path(d))
 def test_preexisting_close_reservation_never_networks(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d)
   reserve(root,'wxentry_test',CLOSE)
   with patch('weex_supervised_reduceonly_close_transport_v4.verify_conditions',side_effect=AssertionError('SHOULD_NOT_CHECK')):
    with self.assertRaisesRegex(CloseDenied,'NEVER_RESEND'):
     send_once('wxentry_test',root=root,approval=lambda *a:True)
if __name__=='__main__':unittest.main()
