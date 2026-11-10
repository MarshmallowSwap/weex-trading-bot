"""Strict close-only behavior of dedicated CROSS-100x supervised adapter; no network."""
import tempfile,json,unittest,sqlite3
from pathlib import Path
from unittest.mock import patch
from weex_supervised_exact_close100_v3 import validate_exact,reserve_close,CloseBlocked,close_one

class Close100Tests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.root=Path(self.tmp.name)
  cfg={'risk':{'minimumLeverage':100},'execution':{'enabled':False,'mode':'PRETRADE'}}
  (self.root/'weex_ai_risk_config.json').write_text(json.dumps(cfg))
  self.client='wxentry_123456789012345678901234'
  self.proof={'status':'VERIFIED_PROTECTED_NEED_EXACT_CLOSE','clientOrderId':self.client,
    'positionId':'77','stopAlgoId':'555','symbol':'ETHUSDT','quantity':'0.001'}
  self.account=([{'id':'77','symbol':'ETHUSDT','side':'LONG','size':'0.001'}],
   [],[{'symbol':'ETHUSDT','algoId':'555'}])
 def verified(self):
  with patch('live_control.state',return_value={'mode':'STOPPED'}),patch('live_control.build_errors',return_value=[]):
   return validate_exact(self.root,self.client,'77',self.account,self.proof)
 def test_exact_close_payload_sdk_serializes_without_network(self):
  self.assertEqual(self.verified(),{'symbol':'ETHUSDT','positionId':77})
 def must_block(self,why):
  with self.assertRaisesRegex(CloseBlocked,why):self.verified()
 def test_wrong_position_id_fails_closed(self):
  self.proof['positionId']='78';self.must_block('PROOF_NOT_BOUND')
 def test_unknown_entry_fails_closed(self):
  self.proof['clientOrderId']='wxentry_other';self.must_block('PROOF_NOT_BOUND')
 def test_unverified_stop_fails_closed(self):
  self.proof['status']='UNVERIFIED';self.must_block('INDEPENDENT_ENTRY')
 def test_wrong_quantity_fails_closed(self):
  self.proof['quantity']='0.002';self.must_block('CLOSE_NOT_TEST_SCOPE')
 def test_other_open_orders_fail_closed(self):
  self.account[1].append({'symbol':'BTCUSDT','orderId':'99'})
  self.must_block('ACCOUNT_NOT_EXACT')
 def test_wrong_position_size_fails_closed(self):
  self.account[0][0]['size']='0.002';self.must_block('EXACT_POSITION_CHANGED')
 def test_no_stop_fails_closed(self):
  self.account[2].clear();self.must_block('EXCHANGE_STOP_CHANGED')
 def test_duplicate_stop_fails_closed(self):
  self.account[2].append({'symbol':'ETHUSDT','algoId':'999'})
  self.must_block('EXCHANGE_STOP_CHANGED')
 def test_100x_mandatory(self):
  p=self.root/'weex_ai_risk_config.json';d=json.loads(p.read_text());d['risk']['minimumLeverage']=50;p.write_text(json.dumps(d))
  self.must_block('PRODUCTION_PRETRADE')
 def test_durable_unknown_close_once_and_no_second_dispatch(self):
  p=self.root/'close.db'
  reserve_close(p,self.client,'77')
  with self.assertRaisesRegex(CloseBlocked,'NO_RETRY'):reserve_close(p,self.client,'77')
  with __import__("contextlib").closing(sqlite3.connect(p)) as c:
   self.assertEqual(c.execute('SELECT status FROM close_intents').fetchone()[0],'UNKNOWN')
 def test_no_live_client_without_authorization(self):
  with self.assertRaisesRegex(CloseBlocked,'AUTHORIZATION_MISSING'):
   close_one(self.client,'77',root=self.root)

if __name__=='__main__':unittest.main()
