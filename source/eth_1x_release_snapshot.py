"""ETHUSDT live 1x pilot single-symbol read-only evidence snapshot.
Does not change exchange parameters or create orders.
"""
import json,urllib.request
from pathlib import Path
from decimal import Decimal
from datetime import datetime,timezone
from monitor import query
R=Path(__file__).resolve().parent
p=query("/capi/v3/account/position/allPosition")
o=query("/capi/v3/openOrders?limit=100&page=0")
c=query("/capi/v3/account/symbolConfig?symbol=ETHUSDT")
if isinstance(c,list):c=next((a for a in c if a.get("symbol")=="ETHUSDT"),{})
if not isinstance(p,list) or not isinstance(o,list) or not isinstance(c,dict):raise RuntimeError("UNAVAILABLE")
with urllib.request.urlopen("https://api-contract.weex.com/capi/v3/market/exchangeInfo?contractType=PERPETUAL",timeout=25) as f:
 symbols=json.load(f)["symbols"]
meta=next(x for x in symbols if x["symbol"]=="ETHUSDT")
with urllib.request.urlopen("https://api-contract.weex.com/capi/v3/market/ticker/24hr",timeout=25) as f:
 tickers=json.load(f)
price=Decimal(str(next(x["lastPrice"] for x in tickers if x.get("symbol")=="ETHUSDT")))
minsize=Decimal(str(meta["minOrderSize"]))
minnotional=minsize*price
checks={"eth_no_open_position":not any(x.get("symbol")=="ETHUSDT" for x in p),
"eth_no_open_order":not any(x.get("symbol")=="ETHUSDT" for x in o),
"cross_mode":c.get("marginType") in ("CROSS","CROSSED"),
"leverage_1x":str(c.get("crossLeverage"))=="1",
"indicative_min_within_5":minnotional<=Decimal("5")}
report={"asOf":datetime.now(timezone.utc).isoformat(),"symbol":"ETHUSDT",
"checks":checks,"referencePrice":str(price),"minOrderSize":str(minsize),
"indicativeMinNotionalUSDT":str(minnotional),"sizeAcceptedByTradingAPI":False,
"closeVerified":False,"botOrderProvenanceVerified":False,
"pilotReady":False,"ordersSubmitted":False}
dest=R/"eth_1x_release_snapshot.json";t=dest.with_suffix(".tmp")
t.write_text(json.dumps(report,indent=2),encoding="utf-8");t.replace(dest)
print("CHECKS",sum(checks.values()),"/",len(checks),"MIN_NOTIONAL",minnotional,"PILOT_READY",False,"ORDERS",0)
