"""WEEX account-vs-symbol leverage observability audit; read-only."""
import json
from pathlib import Path
from datetime import datetime,timezone
from monitor import query
ROOT=Path(__file__).resolve().parent
def run():
 universe=json.loads((ROOT/"universe_latest.json").read_text(encoding="utf-8"))
 account=query("/capi/v3/account/accountConfig")
 positions=query("/capi/v3/account/position/allPosition")
 if not isinstance(positions,list):raise ValueError("Positions unavailable")
 keys=sorted(account.keys()) if isinstance(account,dict) else []
 position_keys=sorted(set().union(*(set(x.keys()) for x in positions))) if positions else []
 report={"asOf":datetime.now(timezone.utc).isoformat(),"accountResponseFields":keys,
 "positionFields":position_keys,"eligiblePairs":universe["count"],
 "accountMaxLeveragePerPairCertified":False,"orderTierLeverageCertified":False,
 "reason":"Need authenticated pair/tier validation for intended 5 USDT margin",
 "ordersSent":False}
 f=ROOT/"account_leverage_audit_latest.json";tmp=f.with_suffix(".tmp")
 tmp.write_text(json.dumps(report,indent=2),encoding="utf-8");tmp.replace(f)
 return report
if __name__=="__main__":
 r=run();print("account fields",r["accountResponseFields"],"positions fields",r["positionFields"],"certified",r["accountMaxLeveragePerPairCertified"])
