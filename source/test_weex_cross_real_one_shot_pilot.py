import unittest
from unittest.mock import patch
from weex_cross_real_one_shot_pilot_20261109 import LimitedTransport,GETS
class OneShotTransportSecurity(unittest.TestCase):
 def setUp(self):
  self.t=LimitedTransport({n:{'path':'/capi/v3/'+n} for n in GETS})
  self.addCleanup(self.t.close)
 def test_wrong_host_rejected(self):
  with self.assertRaises(PermissionError):
   self.t.request('POST','https://api-sim.weex.com/capi/v3/order',data='{}')
 def test_wrong_write_path_rejected(self):
  with self.assertRaises(PermissionError):
   self.t.request('POST','https://api-contract.weex.com/capi/v3/account/leverage',data='{}')
 def test_unreserved_entry_rejected(self):
  with self.assertRaises(PermissionError):
   self.t.request('POST','https://api-contract.weex.com/capi/v3/order',data='{}')
 def test_incorrect_payload_rejected(self):
  self.t.entry={'symbol':'ETHUSDT'}
  with self.assertRaises(PermissionError):
   self.t.request('POST','https://api-contract.weex.com/capi/v3/order',data='{}')
 def test_write_retry_rejected(self):
  self.t.entry={'symbol':'ETHUSDT'};self.t.used.add('ENTRY')
  with self.assertRaises(PermissionError):
   self.t.request('POST','https://api-contract.weex.com/capi/v3/order',data='{"symbol":"ETHUSDT"}')
 def test_cancel_stop_rejected(self):
  with self.assertRaises(PermissionError):
   self.t.request('DELETE','https://api-contract.weex.com/capi/v3/algoOrder?orderId=1')
if __name__=='__main__':unittest.main()
