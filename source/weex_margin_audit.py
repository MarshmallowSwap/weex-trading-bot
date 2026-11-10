"""Read-only 5 USDT margin feasibility estimate, by WEEX symbol."""
import json,urllib.request,urllib.parse,urllib.error,time,math,csv
from decimal import Decimal,ROUND_CEILING
from concurrent.futures import ThreadPoolExecutor,as_completed
from pathlib import Path
ROOT=Path(__file__).resolve().parent
universe=json.loads((ROOT/"universe_latest.json").read_text(encoding="utf-8"))
raw=json.load(urllib.request.urlopen("https://api-contract.weex.com/capi/v3/market/exchangeInfo?contractType=PERPETUAL",timeout=20))
info={s["symbol"]:s for s in raw["symbols"] if isinstance(s,dict) and "symbol" in s}
def D(x):return Decimal(str(x))
def check(s):
    symbol=s["symbol"];i=info[symbol]
    result={"symbol":symbol,"leverageAdvertised":s["maxLeverageAdvertised"]}
    try:
        u="https://api-contract.weex.com/capi/v3/market/klines?"+urllib.parse.urlencode({"symbol":symbol,"interval":"5m","limit":2})
        rows=json.load(urllib.request.urlopen(urllib.request.Request(u,headers={"User-Agent":"WEEX-ReadOnly-CostAudit/1.0"}),timeout=16))
        price=D(sorted(rows,key=lambda r:int(r[0]))[-1][4]); L=D(i["maxLeverage"])
        minimum=D(i["minOrderSize"]);precision=int(i["quantityPrecision"])
        step=D(1).scaleb(-precision)
        if minimum<=0 or price<=0 or L<=0:raise ValueError("Invalid price/minQty/leverage")
        target=(D("5")*L/price)
        qty=(target/step).to_integral_value(rounding="ROUND_FLOOR")*step
        minqty=(minimum/step).to_integral_value(rounding=ROUND_CEILING)*step
        qty=max(qty,minqty)
        notional=qty*price
        required=notional/L
        maker=D(i.get("apiMakerFeeRate") if i.get("apiMakerFeeRate") is not None else i.get("makerFeeRate", "0.0002"))
        taker=D(i.get("apiTakerFeeRate") if i.get("apiTakerFeeRate") is not None else i.get("takerFeeRate","0.0008"))
        result.update(price=str(price),minQty=str(minqty),qtyAt5=str(qty),notionalUSDT=float(notional),
            marginUSDT=float(required),minOrderMarginUSDT=float(minqty*price/L),
            entryFeeTakerUSDT=float(notional*taker),roundTripFeeTakerUSDT=float(notional*taker*2),
            roundTripFeeMakerUSDT=float(notional*maker*2),
            minOrderByQtyFits5=bool(minqty*price/L<=D(5)),
            exactly5MarginBeforeFees=bool(required<=D(5)),
            feeRateTaker=str(taker),feeRateMaker=str(maker),status="ESTIMATE_ONLY")
    except Exception as e:result["status"]="ERROR_"+type(e).__name__
    return result
def main():
    out=[]
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures=[pool.submit(check,s) for s in universe["symbols"]]
        for f in as_completed(futures):out.append(f.result())
    out.sort(key=lambda s:s["symbol"])
    counts={"total":len(out),"estimatedFits5":sum(x.get("minOrderByQtyFits5",False) for x in out),
            "minimumExceeds5":sum(x.get("minOrderByQtyFits5") is False for x in out if x.get("status")=="ESTIMATE_ONLY"),
            "errors":sum(x["status"]!="ESTIMATE_ONLY" for x in out)}
    data={"assumptions":"5 USDT isolated initial margin; maxLeverage from exchange info; fee rates API or public fallback; no account tier/risk brackets, funding, slippage or maintenance margin; quantities rounded using precision; no orders sent",
           "counts":counts,"results":out}
    (ROOT/"weex_margin_5usdt_audit.json").write_text(json.dumps(data,indent=2),encoding="utf-8")
    with (ROOT/"weex_margin_5usdt_audit.csv").open("w",newline="",encoding="utf-8") as handle:
        fields=["symbol","status","leverageAdvertised","price","minQty","minOrderMarginUSDT","qtyAt5","notionalUSDT","marginUSDT","entryFeeTakerUSDT","roundTripFeeTakerUSDT","minOrderByQtyFits5"]
        writer=csv.DictWriter(handle,fieldnames=fields,extrasaction="ignore");writer.writeheader();writer.writerows(out)
    print(json.dumps(counts))
    good=[x for x in out if x.get("status")=="ESTIMATE_ONLY"]
    for x in sorted(good,key=lambda i:i["minOrderMarginUSDT"],reverse=True)[:10]:
        print(x["symbol"],"minMargin",round(x["minOrderMarginUSDT"],4),"feeRoundTrip",round(x["roundTripFeeTakerUSDT"],4))
if __name__=="__main__":main()
