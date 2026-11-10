"""Offline arithmetic only for the persisted 1000 WEEX fills; no HTTP."""
import json,os
from decimal import Decimal as D,InvalidOperation
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parent
def audit(trades):
 reasons={};ids=set();valid=0;quote=D(0);fees=D(0)
 for f in trades:
  why=None
  try:
   fid=str(f['id']);oid=str(f['orderId'])
   q=D(str(f['qty']));p=D(str(f['price']));v=D(str(f['quoteQty']))
   fee=D(str(f['commission']))
   if not fid or fid in ids or not oid:why='DUPLICATE_OR_MISSING_ID'
   elif not all(x.is_finite() for x in (q,p,v,fee)) or min(q,p,v)<=0 or fee<0:
    why='INVALID_NUMERIC_VALUE'
   elif f.get('commissionAsset')!='USDT':why='UNSUPPORTED_COMMISSION_ASSET'
   elif abs(q*p-v)>D('0.00000001'):why='FILL_QUOTE_ARITHMETIC_MISMATCH'
   else:
    valid+=1;quote+=v;fees+=fee
   ids.add(fid)
  except (ValueError,TypeError,KeyError,InvalidOperation):why='MISSING_OR_INVALID_FIELD'
  if why:reasons[why]=reasons.get(why,0)+1
 return {'fillCount':len(trades),'arithmeticVerifiedFills':valid,
   'invalidFills':len(trades)-valid,'failureCounts':reasons,
   'internalFillNotionalUSDT':str(quote),'internalFeesUSDT':str(fees),
   'orderLinkVerificationNotIncluded':True,'fundingNotIncluded':True,
   'economicCertification':False,'releaseGateOverride':False,'exchangeWrites':0}
def run():
 snap=json.loads((ROOT/'weex_trade_1000_snapshot.json').read_text())
 result={'checkedAt':datetime.now(timezone.utc).isoformat(),
   'scope':'PERSISTED_SNAPSHOT_OFFLINE_ARITHMETIC',
   'snapshotAt':snap['checkedAt'],**audit(snap['trades'])}
 path=ROOT/'weex_trade_1000_fill_arithmetic_latest.json'
 tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(result,indent=2));os.replace(tmp,path)
 print(json.dumps(result))
if __name__=='__main__':run()
