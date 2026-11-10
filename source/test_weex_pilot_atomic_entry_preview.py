import unittest
from weex_pilot_atomic_entry_preview import build
class AtomicPreview(unittest.TestCase):
 def test_long(self):
  r=build('LONG','0.002','2200','2100')
  self.assertEqual(r['payload']['slTriggerPrice'],'2100')
  self.assertEqual(r['payload']['SlWorkingType'],'MARK_PRICE')
  self.assertEqual(r['preview']['networkRequests'],0)
 def test_short(self):
  r=build('SHORT','0.002','2200','2300')
  self.assertEqual(r['payload']['side'],'SELL')
  self.assertEqual(r['preview']['networkRequests'],0)
 def test_stop_wrong_side(self):
  for side,stop in [('LONG','2300'),('SHORT','2100')]:
   with self.assertRaises(ValueError):build(side,'0.002','2200',stop)
 def test_oversize(self):
  with self.assertRaises(ValueError):build('LONG','0.011','2200','2100')
if __name__=='__main__':unittest.main()
