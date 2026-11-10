"""ETHUSDT 1x: calculate a bounded LIMIT order quantity from WEEX read-only metadata.
No exchange writes. Do not treat this as proof the exchange accepts the order.
"""
import json,urllib.request
from decimal import Decimal,ROUND_DOWN
from pathlib import Path
from datetime import datetime,timezone
from monitor import query
R=Path(__file__).resolve().parent
p=query("/capi/v3/account/position/allPosition");o=query("/capi/v3/openOrders?limit=100&page=0")
c=query("/capi/v3/account/symbolConfig?symbol=ETHUSDT")
if isinstance(c,list):c=next((a for a in c if a.get("symbol")=="ETHUSDT"),{})
if not isinstance(p,list) or not isinstance(o,list) or not isinstance(c,dict):raise ValueError("ACCOUNT_UNAVAILABLE")
if any(x.get("symbol")=="ETHUSDT" for x in p+o):raise RuntimeError("ETH_BUSY")
if c.get("marginType") not in ("CROSS","CROSSED") or str(c.get("crossLeverage"))!="1":raise RuntimeError("NOT_CROSS_1X")
base="https://api-contract.weex.com"
with urllib.request.urlopen(base+"/capi/v3/market/exchangeInfo?contractType=PERPETUAL",timeout=20) as f:
 meta=next(x for x in json.load(f)["symbols"] if x["symbol"]=="ETHUSDT")
with urllib.request.urlopen(base+"/capi/v3/market/ticker/24hr",timeout=20) as f:
 ticker=next(x for x in json.load(f) if x.get("symbol")=="ETHUSDT")
price=Decimal(str(ticker["lastPrice"]))
minimum=Decimal(str(meta["minOrderSize"]))
precision=int(meta["quantityPrecision"])
step=Decimal(1).scaleb(-precision)
q=(Decimal("5")/price/step).to_integral_value(rounding=ROUND_DOWN)*step
budget=q*price
ok= q>=minimum and budget<=Decimal("5") and q>0
result={"checkedAt":datetime.now(timezone.utc).isoformat(),"symbol":"ETHUSDT",
 "priceReference":str(price),"minimum":str(minimum),"stepDerivedFromPrecision":str(step),
 "calculatedQuantity":str(q),"indicativeNotional":str(budget),
 "within5USDT":ok,"exchangeStepOrFiltersFullyCertified":False,
 "priceMayChange":True,"orderSubmitted":False,"liveReady":False}
target=R/"eth_1x_order_quantity_preview_latest.json";tmp=target.with_suffix(".tmp")
tmp.write_text(json.dumps(result,indent=2),encoding="utf-8");tmp.replace(target)
print("ETH 1X QUANTITY",q,"EST_NOTIONAL",budget,"WITHIN_5",ok,"ORDERS",0)
