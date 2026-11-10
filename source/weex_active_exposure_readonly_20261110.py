from pathlib import Path
from weex_live_worker import Reader
import json,time
r=Reader(Path(__file__).resolve().parent)
p,o,a=r.account()
def slim(x,fields):
 return {k:x.get(k) for k in fields if k in x}
print(json.dumps({"checkedAtEpoch":time.time(),
 "positions":[slim(x,["id","symbol","side","positionSide","size","leverage","marginType","liquidationPrice","entryPrice","markPrice","unrealizedPnl"]) for x in p],
 "regularOrders":[slim(x,["orderId","symbol","side","reduceOnly","status"]) for x in o],
 "conditional":[slim(x,["algoId","symbol","side","positionSide","quantity","reduceOnly","algoStatus","orderType","workingType","triggerPrice","actualOrderId","clientAlgoId"]) for x in a],
 "readOnly":True,"exchangeWrites":0},ensure_ascii=False))
