"""WEEX V3 public risk bracket audit: 5 USDT margin theoretical tiers, read-only."""
import json,urllib.request
from decimal import Decimal,InvalidOperation
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parent
def D(x):return Decimal(str(x))
def run():
 u=json.loads((ROOT/"universe_latest.json").read_text(encoding="utf-8"))
 url="https://api-contract.weex.com/capi/v3/market/riskLimits"
 with urllib.request.urlopen(urllib.request.Request(url,headers={"User-Agent":"WEEX-DESK-RISK-AUDIT/1"}),timeout=25) as r:raw=json.load(r)
 if not isinstance(raw,list):raise ValueError("Unexpected brackets response")
 by={x["symbol"]:x.get("brackets",[]) for x in raw if isinstance(x,dict) and x.get("symbol")}
 results=[]
 for s in u["symbols"]:
  symbol=s["symbol"];lev=D(s["maxLeverageAdvertised"]);notional=lev*D(5)
  brackets=by.get(symbol,[])
  valid=[]
  for b in brackets:
   try:
    floor=D(b["notionalFloor"]);cap=D(b["notionalCap"]);tier=D(b["initialLeverage"])
    if floor<=notional<cap and tier>0:valid.append(tier)
   except (KeyError,InvalidOperation,TypeError):continue
  tiermax=max(valid) if valid else None
  results.append({"symbol":symbol,"advertisedMax":str(lev),"plannedNotionalUSDT":str(notional),
      "tierMaxAtPlannedNotional":str(tiermax) if tiermax is not None else None,
      "publicTierSupportsAdvertised":bool(tiermax is not None and tiermax>=lev)})
 output={"checkedAt":datetime.now(timezone.utc).isoformat(),"universe":len(results),
   "publicRiskLimitEntries":len(by),"tierConfirmed":sum(x["tierMaxAtPlannedNotional"] is not None for x in results),
   "accountSpecificMaxVerified":False,"results":results}
 path=ROOT/"weex_risk_tiers_5usdt_latest.json";temp=path.with_suffix(".tmp")
 temp.write_text(json.dumps(output,indent=2),encoding="utf-8");temp.replace(path)
 return output
if __name__=="__main__":
 x=run();print("pairs",x["universe"],"risk_entries",x["publicRiskLimitEntries"],"tier_matches",x["tierConfirmed"])
 for a in x["results"][:6]:print(a["symbol"],a["advertisedMax"],a["tierMaxAtPlannedNotional"])
