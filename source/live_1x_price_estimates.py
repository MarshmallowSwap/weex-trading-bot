"""Indicative minimum order notional = minOrderSize * lastPrice, no exchange writes."""
import json,urllib.request
from decimal import Decimal,InvalidOperation
from pathlib import Path
R=Path(__file__).resolve().parent
data=json.loads((R/"live_1x_minimum_audit_latest.json").read_text(encoding="utf-8"))
for row in data["symbols"]:
 sym=row["symbol"];cons=row["contractConstraints"]
 try:
  url="https://api-contract.weex.com/capi/v3/market/ticker?symbol="+sym
  with urllib.request.urlopen(url,timeout=12) as f:t=json.load(f)
  p=Decimal(str(t.get("lastPrice") or t.get("last") or t.get("close")))
  q=Decimal(str(cons["minOrderSize"]))
  if not p.is_finite() or not q.is_finite() or p<=0 or q<=0:raise ValueError("invalid")
  n=q*p
  row["indicativeMinNotionalUSDT"]=str(n);row["indicativeWithin5USDT"]=n<=5
 except Exception as e:row["priceCheckError"]=type(e).__name__
data["indicativeCount"]=sum(x.get("indicativeWithin5USDT") is True for x in data["symbols"])
data["minOrderVerified"]=False;data["orderSubmitted"]=False
(R/"live_1x_minimum_audit_latest.json").write_text(json.dumps(data,indent=2),encoding="utf-8")
print("indicative <=5",data["indicativeCount"],"of",len(data["symbols"]))
print([(x["symbol"],x.get("indicativeMinNotionalUSDT"),x.get("priceCheckError")) for x in data["symbols"]])
