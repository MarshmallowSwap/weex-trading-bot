"""Authenticated WEEX official SDK LIVE read-only smoke; never logs credentials."""
import json
from pathlib import Path
from datetime import datetime,timezone
from official_weex_live_sdk_adapter import LiveSdkReadOnly
from weex_common.configuration import ConfigurationRestAPI
from weex_contract_sdk import Contract
ROOT=Path(__file__).resolve().parent
cred=json.loads((ROOT/"weex_credentials.json").read_text(encoding="utf-8"))
config=ConfigurationRestAPI(base_path="https://api-contract.weex.com",
 api_key=cred["api_key"],api_secret=cred["secret_key"],passphrase=cred["passphrase"],
 timeout=12,max_retries=0)
sdk=LiveSdkReadOnly(Contract(config_rest_api=config))
results={}
for name,req in [
 ("positions",("get_capi_v3_account_position_allPosition",{})),
 ("orders",("get_capi_v3_openOrders",{"query":{"page":0,"limit":100}})),
 ("trades",("get_capi_v3_userTrades",{"query":{"limit":100}}))]:
 try:
  response=sdk.execute(*req)
  data=response.data
  results[name]={"statusCode":response.status_code,"responseType":type(data).__name__,
                 "listCount":len(data) if isinstance(data,list) else None}
 except Exception as e:results[name]={"error":type(e).__name__}
result={"at":datetime.now(timezone.utc).isoformat(),"results":results,"writeOperationsEnabled":False}
(ROOT/"official_sdk_authenticated_read_latest.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
print(json.dumps(result))
