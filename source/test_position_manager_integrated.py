import json, tempfile, unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
import position_manager_integrated as mod

class Test(unittest.TestCase):
 def run_with_snapshot(self, snapshot):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder)
   (root/"weex_ai_risk_config.json").write_text(json.dumps({"risk":{"stopLoss":{"enabled":False}}}),encoding="utf-8")
   with patch.object(mod,"ROOT",root),patch("weex_account_observation.observe",return_value=snapshot):
    return mod.run()
 def test_off_and_empty(self):
  snapshot={"positions":[],"conditionalOrders":[],"trailingOrders":[],"observedAt":datetime.now(timezone.utc).isoformat()}
  r=self.run_with_snapshot(snapshot)
  self.assertEqual(r["positions"],0)
  self.assertFalse(r["exchangeWrites"])
 def test_partial_inputs_never_allow_modify(self):
  p=[{"symbol":"BTCUSDT","side":"LONG","size":"2"}]
  b=[{"symbol":"BTCUSDT","positionSide":"LONG","orderType":"TAKE_PROFIT","algoStatus":"NEW","quantity":"1","reduceOnly":True,"algoId":"tp-1"}]
  snapshot={"positions":p,"conditionalOrders":b,"trailingOrders":[],"observedAt":datetime.now(timezone.utc).isoformat()}
  x=self.run_with_snapshot(snapshot)["items"][0]
  self.assertFalse(x["modificationAllowed"])
  self.assertFalse(x["quantitiesCertified"])
 def test_incomplete_snapshot_fails_closed(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder)
   (root/"weex_ai_risk_config.json").write_text(json.dumps({"risk":{"stopLoss":{"enabled":False}}}),encoding="utf-8")
   with patch.object(mod,"ROOT",root),patch("weex_account_observation.observe",side_effect=ValueError("COMPLETE_ACCOUNT_OBSERVATION_UNAVAILABLE")):
    with self.assertRaisesRegex(ValueError,"COMPLETE_ACCOUNT_OBSERVATION_UNAVAILABLE"):
     mod.run()

if __name__=="__main__":unittest.main()
