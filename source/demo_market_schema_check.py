import json,urllib.request
u="https://api-contract.weex.com/capi/v3/market/exchangeInfo?contractType=PERPETUAL"
with urllib.request.urlopen(u,timeout=20) as f:d=json.load(f)
a=d.get("symbols",[])
for x in a:
 if x.get("symbol") in ("BTCUSDT","BTCSUSDT","ETHSUSDT","WAVESUSDT","SUSDT"):
  print(x.get("symbol"),"quoteAsset",x.get("quoteAsset"),"marginAsset",x.get("marginAsset"),"contractType",x.get("contractType"))
print("quotes",sorted({str(x.get("quoteAsset")) for x in a if "SUSDT" in str(x.get("quoteAsset"))}))
