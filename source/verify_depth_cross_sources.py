"""Cross-check WEEX V3 depth with bookTicker and public trade quote quantities."""
import json,urllib.request,urllib.parse
BASE="https://api-contract.weex.com"
def get(path):
 req=urllib.request.Request(BASE+path,headers={"User-Agent":"WEEX-READONLY-VERIFY/1"})
 with urllib.request.urlopen(req,timeout=12) as f:return json.load(f)
for sym in ("BTCUSDT","ETHUSDT","SOLUSDT","1000PEPEUSDT","XPINUSDT"):
 try:
  qs=urllib.parse.urlencode({"symbol":sym})
  b=get("/capi/v3/market/depth?"+qs+"&limit=15")
  top=get("/capi/v3/market/ticker/bookTicker?"+qs)
  trades=get("/capi/v3/market/trades?"+qs+"&limit=2")
  x=top[0] if isinstance(top,list) and top else top
  t=trades[0] if isinstance(trades,list) and trades else {}
  px=float(t.get("price") or 0);qty=float(t.get("qty") or 0);quote=float(t.get("quoteQty") or 0)
  print(sym,"book_vs_ticker",b["bids"][0][1]==x.get("bidQty"),"lastTradeQuoteRatio",round(quote/(qty*px),6) if qty*px else "NA","topPrices",b["bids"][0][0],x.get("bidPrice"))
 except Exception as err:print(sym,type(err).__name__)
