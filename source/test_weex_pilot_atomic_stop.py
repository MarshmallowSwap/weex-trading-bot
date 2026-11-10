import unittest
from weex_isolated_pilot_offline_journal import proposals
from weex_pilot_entry_sdk_adapter import validate_entry
from weex_http_guard import prepare_sdk_request

class AtomicStop(unittest.TestCase):
 def test_long_has_market_price_stop_below_reference(self):
  p=proposals('LONG','0.002','2100',attach_stop=True)['entry']
  self.assertEqual(p['slTriggerPrice'],'2100')
  self.assertEqual(p['SlWorkingType'],'MARK_PRICE')
  self.assertEqual(validate_entry(p,'2200'),p)
  self.assertEqual(prepare_sdk_request('post_capi_v3_order',p)['networkRequests'],0)
 def test_short_stop_above_reference(self):
  p=proposals('SHORT','0.002','2300',attach_stop=True)['entry']
  self.assertEqual(validate_entry(p,'2200'),p)
  self.assertEqual(prepare_sdk_request('post_capi_v3_order',p)['networkRequests'],0)
 def test_long_rejects_wrong_side(self):
  p=proposals('LONG','0.002','2300',attach_stop=True)['entry']
  with self.assertRaisesRegex(ValueError,'INVALID_ATTACHED_STOP'):
   validate_entry(p,'2200')
 def test_short_rejects_wrong_side(self):
  p=proposals('SHORT','0.002','2100',attach_stop=True)['entry']
  with self.assertRaisesRegex(ValueError,'INVALID_ATTACHED_STOP'):
   validate_entry(p,'2200')
 def test_rejects_unpaired_stop_fields(self):
  p=proposals('SHORT','0.002','2300',attach_stop=True)['entry']
  del p['SlWorkingType']
  with self.assertRaisesRegex(ValueError,'INVALID_ENTRY_FIELDS'):
   validate_entry(p,'2200')
if __name__=='__main__':unittest.main()
