"""WEEX position snapshots, no orders; do not infer missing prices."""
import json
from pathlib import Path
from datetime import datetime,timezone
from monitor import query
ROOT=Path(__file__).resolve().parent
KEYS=("symbol","side","size","openValue","cumOpenSize","cumOpenValue",
      "openFee","cumOpenFee","cumCloseFee","fundingFee","cumFundingFee",
      "liquidatePrice","marginType","isolatedMargin","marginSize","leverage",
      "unrealizePnl","updatedTime")
def snapshot():
    from weex_account_observation import load
    shared=load(ROOT,max_age=300)
    data=shared['positions'] if shared else query('/capi/v3/account/position/allPosition')
    if not isinstance(data,list):raise ValueError("Positions endpoint did not return list")
    items=[]
    for p in data:
        if not isinstance(p,dict) or not p.get("symbol"):continue
        items.append({k:p[k] for k in KEYS if k in p})
    output={"observedAt":shared["observedAt"] if shared else datetime.now(timezone.utc).isoformat(),"readOnly":True,
            "count":len(items),"positions":items}
    tmp=ROOT/"positions_readonly.tmp"
    tmp.write_text(json.dumps(output,indent=2),encoding="utf-8")
    tmp.replace(ROOT/"positions_readonly_latest.json")
    return output
if __name__=="__main__":
    out=snapshot()
    print("count",out["count"])
    for p in out["positions"]:
        print("symbol",p["symbol"],"side",p.get("side"),"has_liquidation",bool(p.get("liquidatePrice")),"has_leverage",bool(p.get("leverage")))
