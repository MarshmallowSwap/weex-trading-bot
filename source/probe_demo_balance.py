"""Read-only WEEX demo balance probe. No trading, no account details exposed."""
from monitor import query
from weex_demo_firewall import authorize,BASE
path="/capi/v3/sim/balance"
assert authorize("GET",BASE+path)["allowed"]
try:
 data=query(path)
 if not isinstance(data,list):raise ValueError("Unexpected demo account response")
 print("demo_endpoint=OK","assets",[(str(x.get("asset")),bool(float(x.get("availableBalance",0))>0)) for x in data if isinstance(x,dict)])
except Exception as e:
 print("demo_endpoint=NOT_VERIFIED",type(e).__name__,str(e)[:160])
