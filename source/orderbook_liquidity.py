"""Read-only WEEX futures order-book liquidity audit across the eligible universe."""
import json,urllib.request,urllib.parse,time,concurrent.futures
from pathlib import Path
from datetime import datetime,timezone
from decimal import Decimal
from weex_depth_evidence import verify as verify_units
ROOT=Path(__file__).resolve().parent
URL="https://api-contract.weex.com/capi/v3/market/depth?"

def parse_book(symbol,data,*,metadata=None,evidence=None):
 """Validate and sort the actual top 15 levels; never certify unspecified units."""
 levels={}
 for side in ("bids","asks"):
  raw=data.get(side)
  if not isinstance(raw,list) or not raw:raise ValueError("MISSING_BOOK_SIDE")
  parsed=[]
  for row in raw:
   if not isinstance(row,(list,tuple)) or len(row)!=2:raise ValueError("INVALID_BOOK_LEVEL")
   price,size=(Decimal(str(v)) for v in row)
   if not price.is_finite() or not size.is_finite() or price<=0 or size<0:raise ValueError("INVALID_BOOK_NUMBER")
   if size:parsed.append((price,size))
  if not parsed:raise ValueError("EMPTY_BOOK_SIDE")
  if len({p for p,q in parsed})!=len(parsed):raise ValueError("DUPLICATE_PRICE_LEVEL")
  levels[side]=sorted(parsed,reverse=side=="bids")[:15]
 bid=levels["bids"][0][0];ask=levels["asks"][0][0]
 if ask<=bid:raise ValueError("CROSSED_BOOK")
 result={"symbol":symbol,"status":"OK","spreadBps":float((ask-bid)/((ask+bid)/2)*10000),
  "bestBid":str(bid),"bestAsk":str(ask),"top15BidNotional":None,"top15AskNotional":None,
  "depthUnitVerified":False,"depthUnitStatus":"V3_DOCUMENTATION_DOES_NOT_SPECIFY_SIZE_UNIT",
  "rawPriceTimesSizeBid":float(sum(p*q for p,q in levels["bids"])),
  "rawPriceTimesSizeAsk":float(sum(p*q for p,q in levels["asks"])),
  "bookUpdateId":data.get("lastUpdateId"),"receivedAt":datetime.now(timezone.utc).isoformat(),
  "levelsUsed":{side:len(rows) for side,rows in levels.items()}}
 if metadata is not None:
  valid,basis=verify_units(symbol,metadata,data,evidence)
  result.update(depthUnitVerified=valid,depthUnitStatus=basis,depthUnitOfficiallyConfirmed=False)
  if valid:
   result.update(top15BidNotional=result['rawPriceTimesSizeBid'],top15AskNotional=result['rawPriceTimesSizeAsk'],
                 depthQuantityUnit=metadata['baseAsset'],notionalFormula='price * size',contractValApplied=False)
 return result

def inspect(symbol, *, opener=None):
 from weex_api_budget import open_url
 opener=opener or open_url
 try:
  url=URL+urllib.parse.urlencode({"symbol":symbol})
  req=urllib.request.Request(url,headers={"User-Agent":"WEEX-AI-DESK-READONLY/1.0"})
  with opener(req,timeout=12) as resp: data=json.load(resp)
  evidence_path=ROOT/'weex_depth_unit_evidence.json'
  try:evidence=json.loads(evidence_path.read_text(encoding='utf-8'))
  except (ValueError,OSError):evidence={}
  metadata=None
  if symbol in evidence.get('symbols',{}):
   meta_url='https://api-contract.weex.com/capi/v3/market/exchangeInfo?'+urllib.parse.urlencode({'symbol':symbol})
   with opener(meta_url,timeout=12) as resp: meta_data=json.load(resp)
   metadata=next(x for x in meta_data['symbols'] if x['symbol']==symbol)
  return parse_book(symbol,data,metadata=metadata,evidence=evidence)
 except Exception as exc:return {"symbol":symbol,"status":"ERROR","reason":type(exc).__name__}
def run(limit=40):
 universe=json.loads((ROOT/"universe_latest.json").read_text(encoding="utf-8"))
 symbols=[x["symbol"] for x in universe["symbols"][:limit]]
 with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
  results=list(pool.map(inspect,symbols))
 result={"asOf":datetime.now(timezone.utc).isoformat(),"source":"WEEX V3 public order books","sampled":len(results),"valid":sum(x["status"]=="OK" for x in results),"results":results,"tradingEnabled":False}
 tmp=ROOT/"orderbook_audit.tmp";tmp.write_text(json.dumps(result,indent=2),encoding="utf-8");tmp.replace(ROOT/"orderbook_audit_latest.json")
 return result
if __name__=="__main__":
 r=run();print("checked",r["sampled"],"valid",r["valid"],"errors",r["sampled"]-r["valid"])
 for x in r["results"][:6]:print(x["symbol"],x["status"],x.get("spreadBps"))
