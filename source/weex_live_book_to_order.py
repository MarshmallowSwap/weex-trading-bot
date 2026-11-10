"""Official WEEX SDK live depth -> timestamped executable-price quote.
No order submission, no credential logging.
"""
from datetime import datetime,timezone
from decimal import Decimal
from weex_contract_sdk import Contract
from weex_common.configuration import ConfigurationRestAPI
from weex_live_preflight import fresh_order
def get_quote(symbol="ETHUSDT",*,client=None):
 if symbol!="ETHUSDT":raise ValueError("PILOT_ONLY")
 client=client or Contract(config_rest_api=ConfigurationRestAPI(base_path="https://api-contract.weex.com"))
 response=client.rest_api.execute_operation("get_capi_v3_market_depth",{"query":{"symbol":symbol}})
 if response.status_code!=200 or not isinstance(response.data,dict):raise ValueError("DEPTH_FAILED")
 book=response.data
 bids=book.get("bids") or [];asks=book.get("asks") or []
 if not bids or not asks:raise ValueError("EMPTY_BOOK")
 bid=Decimal(str(bids[0][0]));ask=Decimal(str(asks[0][0]))
 if not bid.is_finite() or not ask.is_finite() or bid<=0 or ask<=bid:raise ValueError("INVALID_BOOK")
 return {"symbol":symbol,"bid":str(bid),"ask":str(ask),
         "timestampMs":int(datetime.now(timezone.utc).timestamp()*1000),
         "lastUpdateId":book.get("lastUpdateId"),"source":"OFFICIAL_WEEX_DEPTH"}
def preview(*,side="LONG",quantity="0.002",tp_price="2450",client_order_id="wxpilot_preview",client=None):
 q=get_quote(client=client)
 order=fresh_order(symbol="ETHUSDT",side=side,quantity=quantity,
                   tp_price=tp_price,client_order_id=client_order_id,quote=q)
 return {"source":q["source"],"bid":q["bid"],"ask":q["ask"],"order":order,
         "submitted":False}
if __name__=="__main__":
 import json
 print(json.dumps(preview(),sort_keys=True))
