import unittest,json
from pathlib import Path
from risk_gate import evaluate
CFG=json.loads((Path(__file__).parent/"weex_ai_risk_config.json").read_text(encoding="utf-8"))
C={"marginUSDT":5,"leverage":100,"accountMaxLeverage":100,"marketDataStatus":"FRESH","bookDepthUnitVerified":True,"executionCostsVerified":True,"positionReconciled":True,"side":"LONG","openPositionCount":0}
class GateTests(unittest.TestCase):
 def test_live_disabled(self):
  x=evaluate(C,CFG)
  self.assertFalse(x["approved"]);self.assertIn("LIVE_DISABLED",x["reasons"])
 def test_unverified_depth(self):
  x=evaluate(dict(C,bookDepthUnitVerified=False),CFG)
  self.assertIn("BOOK_UNITS_NOT_VERIFIED",x["reasons"])
 def test_excess_leverage(self):
  x=evaluate(dict(C,leverage=200),CFG)
  self.assertIn("ABOVE_ACCOUNT_LEVERAGE",x["reasons"])
 def test_position_limit(self):
  x=evaluate(dict(C,openPositionCount=10),CFG)
  self.assertIn("POSITION_LIMIT",x["reasons"])
if __name__=="__main__":unittest.main()
