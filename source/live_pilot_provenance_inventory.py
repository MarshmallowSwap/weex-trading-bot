"""Read-only WEEX LIVE pilot provenance inventory; account snapshots, no writes."""
from monitor import query
from pathlib import Path
from datetime import datetime,timezone
import json
R=Path(__file__).resolve().parent
positions=query("/capi/v3/account/position/allPosition")
trades=query("/capi/v3/userTrades?limit=100")
history=query("/capi/v3/order/history?limit=100&page=0")
if not all(isinstance(x,list) for x in (positions,trades,history)):raise RuntimeError("INVALID_WEEX_RESPONSE")
orderids={str(x.get("orderId")):x for x in history if isinstance(x,dict) and x.get("orderId")}
matches=sum(str(t.get("orderId")) in orderids for t in trades if isinstance(t,dict))
result={"at":datetime.now(timezone.utc).isoformat(),"positions":len(positions),
"tradesInWindow":len(trades),"ordersInWindow":len(history),
"tradesWithMatchingHistoryOrder":matches,"botOwnedOrdersProven":0,
"manualPositionsExcluded":True,"autoCloseAllowed":False,"exchangeWrites":False}
p=R/"live_pilot_provenance_inventory_latest.json";tmp=p.with_suffix(".tmp")
tmp.write_text(json.dumps(result,indent=2),encoding="utf-8");tmp.replace(p)
print("positions",len(positions),"trades",len(trades),"history",len(history),"trade_order_matches",matches,"bot_owned",0,"live_writes",False)
