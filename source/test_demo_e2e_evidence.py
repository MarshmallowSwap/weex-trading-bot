import unittest
from demo_e2e_evidence import evaluate
class T(unittest.TestCase):
 def test_empty_failclosed(self):
  self.assertFalse(evaluate({}, {}, {})["ready"])
 def test_mock_evidence_cannot_approve(self):
  h={"balance":{"accessible":True},"positions":{"accessible":True}}
  r={"certified":True,"intents":[{"clientId":"x"}]}
  e={"exchangeVerified":True,"closeEndpoint":{"dedicatedDemo":True},"realEndpointsUsed":False}
  self.assertFalse(evaluate(h,r,e)["ready"])
 def test_no_real_endpoint(self):
  self.assertFalse(evaluate({}, {}, {"realEndpointsUsed":True})["checks"]["no_real_endpoint_used"])
if __name__=="__main__":unittest.main()
