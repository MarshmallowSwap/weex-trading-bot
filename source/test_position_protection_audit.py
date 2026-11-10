import unittest
from position_protection_audit import assess
class TestCoverage(unittest.TestCase):
 def test_no_protection_is_uncertified(self):
  a=assess({"symbol":"BTCUSDT","side":"LONG","size":"0.01"},[])
  self.assertEqual(a["activeCandidates"],0)
  self.assertFalse(a["safeToReplace"])
 def test_protection_still_uncertified(self):
  a=assess({"symbol":"BTCUSDT","side":"LONG","size":"0.01"},
           [{"symbol":"BTCUSDT","positionSide":"LONG","algoStatus":"NEW","quantity":"0.01"}])
  self.assertEqual(a["activeCandidates"],1)
  self.assertEqual(a["status"],"UNCERTIFIED_COVERAGE")
 def test_mismatch_not_counted(self):
  a=assess({"symbol":"BTCUSDT","side":"LONG","size":"0.01"},
           [{"symbol":"BTCUSDT","positionSide":"SHORT","algoStatus":"NEW"}])
  self.assertEqual(a["protectionCandidates"],0)
 def test_invalid_quantity(self):
  self.assertEqual(assess({"symbol":"BTCUSDT","side":"LONG","size":"invalid"},[])["status"],"UNKNOWN")
if __name__=="__main__":unittest.main()
