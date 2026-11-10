import sys
sys.path.insert(0,r"D:\FUNDSHOT\weex_alerts")
from monitor import query
positions=query("/capi/v3/account/position/allPosition")
print("COUNT",len(positions))
for p in positions:
 print("POSITION_FIELDS",[(k,str(v)[:90]) for k,v in p.items() if k.lower() not in ("apikey","secret","passphrase")])
