from weex_api_budget import open_url
"""WEEX perpetual universe refresh, read-only. Fails closed, atomic snapshot."""
import json, os, urllib.request
from datetime import datetime, timezone
from pathlib import Path
URL="https://api-contract.weex.com/capi/v3/market/exchangeInfo?contractType=PERPETUAL"
ROOT=Path(__file__).resolve().parent
OUT=ROOT/"universe_latest.json"
MIN_LEVERAGE=100

def api_trading_symbols():
    request=urllib.request.Request('https://api-contract.weex.com/capi/v3/market/apiTradingSymbols',headers={'User-Agent':'WEEX-ReadOnly/1'})
    with open_url(request,timeout=15) as response: data=json.load(response)
    if not isinstance(data,list) or not data or any(not isinstance(x,str) or not x for x in data):
        raise ValueError('INVALID_API_TRADING_SYMBOLS')
    return set(data)
def universe():
    req=urllib.request.Request(URL,headers={"User-Agent":"WEEX-AI-Desk-Discovery/0.2"})
    with open_url(req,timeout=20) as response:
        data=json.load(response)
    if not isinstance(data,dict) or not isinstance(data.get("symbols"),list) or not data["symbols"]:
        raise ValueError("WEEX returned invalid/empty symbols: keeping last valid snapshot")
    symbols={}
    api_allowed=api_trading_symbols()
    excluded=[]
    valid=0
    for s in data["symbols"]:
        if not isinstance(s,dict): continue
        try: leverage=float(s["maxLeverage"])
        except (KeyError,ValueError,TypeError): continue
        if s.get("contractType")!="PERPETUAL" or s.get("quoteAsset")!="USDT" or not s.get("symbol"):continue
        valid+=1
        if leverage<MIN_LEVERAGE:continue
        if s['symbol'] not in api_allowed:
            excluded.append(s['symbol'])
            continue
        symbols[s["symbol"]]={
            "symbol":s["symbol"],"maxLeverageAdvertised":leverage,
            "minLeverage":s.get("minLeverage"),"minOrderSize":s.get("minOrderSize"),
            "quantityPrecision":s.get("quantityPrecision"),"contractVal":s.get("contractVal"),
            "apiTakerFeeRate":s.get("apiTakerFeeRate")}
    if not valid:raise ValueError("No valid perpetual symbols: keeping last valid snapshot")
    eligible=sorted(symbols.values(),key=lambda x:(-x["maxLeverageAdvertised"],x["symbol"]))
    return {"scannedAt":datetime.now(timezone.utc).isoformat(),"source":URL,
            "minLeverageFilter":MIN_LEVERAGE,"count":len(eligible),"symbols":eligible,
            "apiTradingSymbolsChecked":True,"excludedNotApiEnabled":sorted(excluded),
            "warning":"Exchange-advertised leverage, not individual account/tier leverage. No order capability."}
def update():
    new=universe()
    old={}
    if OUT.exists():
        previous=json.loads(OUT.read_text(encoding="utf-8"))
        old={s["symbol"]:s["maxLeverageAdvertised"] for s in previous.get("symbols",[])}
    current={s["symbol"]:s["maxLeverageAdvertised"] for s in new["symbols"]}
    new["changes"]={
        "added":sorted(set(current)-set(old)),
        "removed":sorted(set(old)-set(current)),
        "leverageChanged":sorted(s for s in set(old)&set(current) if old[s]!=current[s])}
    tmp=OUT.with_suffix(".tmp")
    tmp.write_text(json.dumps(new,indent=2),encoding="utf-8")
    os.replace(tmp,OUT)
    print("WEEX eligible >=",MIN_LEVERAGE,"x:",new["count"])
    for key,values in new["changes"].items():print(key,len(values),", ".join(values[:15]))
    return new
if __name__=="__main__":update()
