"""Read-only exchangeInfo min size audit. No execution or account changes."""
import json,urllib.request
from pathlib import Path
from decimal import Decimal,InvalidOperation
from datetime import datetime,timezone
R=Path(__file__).resolve().parent
u=json.loads((R/"live_1x_candidates_latest.json").read_text(encoding="utf-8"))
url="https://api-contract.weex.com/capi/v3/market/exchangeInfo?contractType=PERPETUAL"
with urllib.request.urlopen(url,timeout=25) as response: raw=json.load(response)
symbols={r["symbol"]:r for r in raw.get("symbols",[]) if isinstance(r,dict) and r.get("symbol")}
output=[]
for x in u["pilotCandidates"]:
 s=x["symbol"];meta=symbols.get(s,{})
 keys={k:str(v) for k,v in meta.items() if any(q in k.lower() for q in ("min","step","tick","contractval","quantity","notional"))}
 output.append({"symbol":s,"contractConstraints":keys,"crossLeverageConfigured":x.get("crossLeverage"),
   "minNotionalAt1xVerified":False,"eligibleForRealOrder":False})
report={"at":datetime.now(timezone.utc).isoformat(),"symbols":output,"minOrderVerified":False,
"orderSubmitted":False,"reason":"ExchangeInfo fields alone do not prove minimum actual executable notional at 1x"}
p=R/"live_1x_minimum_audit_latest.json";tmp=p.with_suffix(".tmp");tmp.write_text(json.dumps(report,indent=2),encoding="utf-8");tmp.replace(p)
print("audited",len(output))
for x in output[:6]:print(x["symbol"],x["contractConstraints"])
