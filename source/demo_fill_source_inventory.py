"""Safe WEEX demo order schema inventory; authenticated GET only.
Never exposes account secrets or submits orders.
"""
from monitor import query
import json
from pathlib import Path
from datetime import datetime,timezone
paths={"/capi/v3/sim/order/history?symbol=BTCSUSDT&limit=100&page=0":"demo_history","/capi/v3/sim/position/allPosition":"demo_positions"}
out={"checkedAt":datetime.now(timezone.utc).isoformat(),"writes":False,"sources":{}}
for path,name in paths.items():
 try:
  data=query(path)
  if not isinstance(data,list):raise ValueError("UNEXPECTED_SCHEMA")
  out["sources"][name]={"ok":True,"count":len(data),"fields":sorted(set().union(*(set(x.keys()) for x in data if isinstance(x,dict)))) if data else []}
 except Exception as e:out["sources"][name]={"ok":False,"error":type(e).__name__}
root=Path(__file__).resolve().parent
(root/"demo_fill_source_inventory_latest.json").write_text(json.dumps(out,indent=2),encoding="utf-8")
print(json.dumps(out))
