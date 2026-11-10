"""WEEX demo-only account health and catalog: no orders."""
import json
from datetime import datetime,timezone
from pathlib import Path
from monitor import query
from weex_demo_firewall import authorize,BASE,DEMO_SYMBOLS
root=Path(__file__).resolve().parent
out={"checkedAt":datetime.now(timezone.utc).isoformat(),"demoSymbolsDocumented":sorted(DEMO_SYMBOLS),"verifiedCompleteUniverse":False,"ordersSubmitted":0}
for name,path in (("balance","/capi/v3/sim/balance"),("positions","/capi/v3/sim/position/allPosition")):
 try:
  assert authorize("GET",BASE+path)["allowed"]
  rows=query(path)
  if not isinstance(rows,list):raise ValueError("Unexpected schema")
  out[name]={"accessible":True,"rows":len(rows)}
  if name=="balance":out[name]["assets"]=[str(x.get("asset")) for x in rows if isinstance(x,dict)]
  if name=="positions":out[name]["symbols"]=[str(x.get("symbol")) for x in rows if isinstance(x,dict)]
 except Exception as e:out[name]={"accessible":False,"error":type(e).__name__}
p=root/"demo_health_latest.json";temp=p.with_suffix(".tmp");temp.write_text(json.dumps(out,indent=2),encoding="utf-8");temp.replace(p)
print(json.dumps(out))
