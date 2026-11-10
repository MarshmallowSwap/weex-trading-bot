"""Read-only min-notional estimates using official futures 24hr tickers."""
import json,urllib.request
from pathlib import Path
from decimal import Decimal
from datetime import datetime,timezone
R=Path(__file__).resolve().parent
data=json.loads((R/"live_1x_minimum_audit_latest.json").read_text(encoding="utf-8"))
url="https://api-contract.weex.com/capi/v3/market/ticker/24hr"
with urllib.request.urlopen(urllib.request.Request(url,headers={"User-Agent":"WEEX-DESK-AUDIT/1"}),timeout=25) as f: tickers=json.load(f)
if not isinstance(tickers,list):raise ValueError("INVALID_TICKER_SCHEMA")
price={r["symbol"]:Decimal(str(r["lastPrice"])) for r in tickers if isinstance(r,dict) and r.get("symbol") and r.get("lastPrice")}
for row in data["symbols"]:
 p=price.get(row["symbol"])
 try:
  minimum=Decimal(str(row["contractConstraints"]["minOrderSize"]))
  if not p or p<=0 or minimum<=0:raise ValueError("INVALID_PRICE_OR_QUANTITY")
  notion=p*minimum
  row["lastPriceUSDT"]=str(p);row["indicativeMinNotionalUSDT"]=str(notion)
  row["indicativeWithin5USDT"]=notion<=Decimal("5")
 except Exception as e:row["priceCheckError"]=type(e).__name__
data["checkedAt"]=datetime.now(timezone.utc).isoformat()
data["pricesVerified"]=sum("lastPriceUSDT" in x for x in data["symbols"])
data["indicativeCount"]=sum(x.get("indicativeWithin5USDT") is True for x in data["symbols"])
data["minOrderVerified"]=False
data["orderSubmitted"]=False
p=R/"live_1x_minimum_audit_latest.json";t=p.with_suffix(".tmp")
t.write_text(json.dumps(data,indent=2),encoding="utf-8");t.replace(p)
print("PRICES",data["pricesVerified"],"WITHIN_5",data["indicativeCount"])
for r in data["symbols"]:print(r["symbol"],r.get("indicativeMinNotionalUSDT","N/A"),r.get("indicativeWithin5USDT","UNKNOWN"))
