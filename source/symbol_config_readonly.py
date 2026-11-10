"""WEEX per-symbol authenticated settings: GET only; no leverage changes."""
import json
from pathlib import Path
from datetime import datetime,timezone
from monitor import query
ROOT=Path(__file__).resolve().parent
u=json.loads((ROOT/"universe_latest.json").read_text(encoding="utf-8"))
symbols={s["symbol"]:s for s in u["symbols"]}
samples=("BTCUSDT","ETHUSDT","SOLUSDT","BANANAUSDT","CELRUSDT")
rows=[]
for symbol in samples:
 try:
  result=query("/capi/v3/account/symbolConfig?symbol="+symbol)
  records=result if isinstance(result,list) else [result]
  records=[r for r in records if isinstance(r,dict) and r.get("symbol")==symbol]
  if len(records)!=1:raise ValueError("Missing or ambiguous symbol")
  r=records[0]
  rows.append({"symbol":symbol,"status":"OK","marginType":r.get("marginType"),
               "isolatedLongLeverage":r.get("isolatedLongLeverage"),
               "isolatedShortLeverage":r.get("isolatedShortLeverage"),
               "crossLeverage":r.get("crossLeverage"),
               "advertisedMax":symbols[symbol]["maxLeverageAdvertised"]})
 except Exception as e:rows.append({"symbol":symbol,"status":type(e).__name__})
output={"at":datetime.now(timezone.utc).isoformat(),"readOnly":True,"accountSample":rows,
        "note":"Configured account leverage is not maximum allowed leverage; no change attempted"}
(ROOT/"symbol_config_readonly_latest.json").write_text(json.dumps(output,indent=2),encoding="utf-8")
for r in rows:print(r)
