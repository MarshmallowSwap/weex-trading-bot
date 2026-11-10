"""Offline tests for one-time live ETH100 leverage mutation; no network."""
import unittest,json,tempfile
from pathlib import Path
from unittest.mock import patch,Mock
import weex_eth_100x_leverage_setup_once as mod

class OneTimeSettingTests(unittest.TestCase):
 def test_exact_setting(self):
  self.assertEqual(mod.BODY,{'symbol':'ETHUSDT','marginType':'CROSSED','crossLeverage':'100'})
 def test_transport_rejects_other_symbol_and_order_endpoint(self):
  t=mod.OnlyLeverage()
  self.addCleanup(t.close)
  with self.assertRaises(PermissionError):
   t.request('POST','https://api-contract.weex.com/capi/v3/order',
             data=json.dumps(mod.BODY))
  self.assertEqual(t.attempts,0)
 def test_transport_does_not_repeat_post(self):
  t=mod.OnlyLeverage();self.addCleanup(t.close)
  t.attempts=1
  with self.assertRaises(PermissionError):
   t.request('POST','https://api-contract.weex.com/capi/v3/account/leverage',
      data=json.dumps(mod.BODY))
  self.assertEqual(t.attempts,1)
 def test_payload_mismatch_never_dispatches(self):
  t=mod.OnlyLeverage();self.addCleanup(t.close)
  with self.assertRaises(PermissionError):
   t.request('POST','https://api-contract.weex.com/capi/v3/account/leverage',
       data=json.dumps(dict(mod.BODY,crossLeverage='400')))
  self.assertEqual(t.attempts,0)
 def test_known_reserved_attempt_no_retry(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d)
   record=root/'reserved.json'
   record.write_text(json.dumps({'status':'REQUEST_RESERVED'}))
   with patch.object(mod,'STATE',record),patch('weex_eth_100x_leverage_setup_once.Reader') as reader:
    with patch('weex_eth_100x_leverage_setup_once.preflight',side_effect=AssertionError('SHOULD_NOT_PREFLIGHT')):
     with patch('weex_eth_100x_leverage_setup_once.OnlyLeverage',side_effect=AssertionError('SHOULD_NOT_SEND')):
      reader.return_value.read.return_value=[{'symbol':'ETHUSDT','marginType':'CROSSED','separatedType':'COMBINED','crossLeverage':'50'}]
      result=mod.run()
      self.assertEqual(result['status'],'UNKNOWN_NO_RETRY')
 def test_known_verified_readback_never_sends_again(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d)
   record=root/'reserved.json'
   record.write_text(json.dumps({'status':'REQUEST_RESERVED'}))
   with patch.object(mod,'STATE',record),patch('weex_eth_100x_leverage_setup_once.Reader') as reader:
    with patch('weex_eth_100x_leverage_setup_once.OnlyLeverage',side_effect=AssertionError('SHOULD_NOT_SEND')):
     reader.return_value.read.return_value=[{'symbol':'ETHUSDT','marginType':'CROSSED','separatedType':'COMBINED','crossLeverage':'100'}]
     self.assertEqual(mod.run()['status'],'VERIFIED_FROM_READBACK_NO_RESEND')

if __name__=='__main__':unittest.main()
