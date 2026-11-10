"""WEEX depth dimensional verification report; no speculative unit conversion."""
import json
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parent
checks={"BTCUSDT":{"contractVal":"0.0001","topBidSize":"2.9850"},
"ETHUSDT":{"contractVal":"0.001","topBidSize":"43.441"},
"SOLUSDT":{"contractVal":"0.1","topBidSize":"1147.4"},
"1000PEPEUSDT":{"contractVal":"100","topBidSize":"950000"},
"XPINUSDT":{"contractVal":"1000","topBidSize":"829000"}}
report={"checkedAt":datetime.now(timezone.utc).isoformat(),
 "v3BookUnits":"NOT_VERIFIED","priceTimesSizeMayBeBaseCurrencyNotional":True,
 "contractValMultiplierMustNotBeAppliedWithoutEvidence":True,
 "checkedSymbols":checks,
 "piusdt":{"candles":"HTTP_400","depth":"HTTP_200","interpretation":"candle feed unavailable for requested parameters; skip symbol for diagnostic trading"},
 "liquidityGate":"FAIL_CLOSED","liveOrdersEnabled":False}
target=ROOT/"depth_units_validation_latest.json"
target.write_text(json.dumps(report,indent=2),encoding="utf-8")
print("units",report["v3BookUnits"],"piCandles",report["piusdt"]["candles"],"gate",report["liquidityGate"])
