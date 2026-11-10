import unittest
from protection_policy import classify
class PolicyTests(unittest.TestCase):
 def test_sl_off(self):
  self.assertEqual(classify({"verified":True,"slCovered":False},False)["status"],"SL_OFF_BY_CONFIGURATION")
 def test_missing_coverage(self):
  self.assertEqual(classify({"verified":True,"slCovered":False},True)["status"],"STOP_COVERAGE_GAP")
 def test_unknown(self):
  self.assertEqual(classify({"verified":False,"reason":"PAGINATION_INCOMPLETE"},False)["status"],"UNVERIFIED")
 def test_candidate(self):
  self.assertEqual(classify({"verified":True,"slCovered":True},True)["status"],"COVERAGE_CANDIDATE")
if __name__=="__main__":unittest.main()
