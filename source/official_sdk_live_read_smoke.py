"""Live SDK public-market read smoke test, no credentials or write operations."""
import json
from pathlib import Path
from datetime import datetime,timezone
from official_weex_live_sdk_adapter import LiveSdkReadOnly
R=Path(__file__).resolve().parent
api=LiveSdkReadOnly()
response=api.execute("get_capi_v3_market_depth",{"query":{"symbol":"ETHUSDT","limit":15}})
data=getattr(response,"data",None)
report={"checkedAt":datetime.now(timezone.utc).isoformat(),
"symbol":"ETHUSDT","operation":"get_capi_v3_market_depth",
"statusCode":getattr(response,"status_code",None),
"responseType":type(data).__name__,
"hasResponse":data is not None,"writesEnabled":False}
(R/"official_sdk_live_read_latest.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
print(report)
