import unittest,tempfile
from pathlib import Path
from unittest.mock import patch
import weex_agent_orchestrator as o
CFG={"execution":{"enabled":False},"risk":{"marginModePreference":"cross"}}
MARKET={"asOf":"2026-10-22T21:00:00+00:00","results":[{"symbol":"BTCUSDT","trend":{"aligned":True},"momentum":{"confirmed":True},"realOrderBook":{"passed":False}}]}
POS={"asOf":"2026-10-22T21:00:00+00:00"}
class Test(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory()
  self.addCleanup(self.temp.cleanup)
  self.root_patch=patch.object(o,'ROOT',Path(self.temp.name))
  self.root_patch.start();self.addCleanup(self.root_patch.stop)
 def run_case(self,cfg=CFG,fresh=True):
  with patch.object(o,"load",side_effect=lambda n:{"weex_ai_risk_config.json":cfg,"market_agents_latest.json":MARKET,"position_manager_integrated_latest.json":POS,"live_release_gate_latest.json":{"gate":"NO_GO"}}[n]),patch.object(o,"recent",return_value=fresh):
   return o.cycle()
 def test_shadow(self):
  x=self.run_case()
  self.assertFalse(x["ordersSubmitted"]);self.assertEqual(x["signals"][0]["strategyAgent"],"WAIT")
 def test_stale(self):self.assertEqual(self.run_case(fresh=False)["cycleStatus"],"DEGRADED")
 def test_live_enabled_is_not_silent(self):
  x=self.run_case(cfg={"execution":{"enabled":True},"risk":{"marginModePreference":"cross"}})
  self.assertEqual(x["cycleStatus"],"DEGRADED")
 def test_manual(self):self.assertTrue(self.run_case()["manualPositionsUntouched"])
if __name__=="__main__":unittest.main()
