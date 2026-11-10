"""WEEX Futures SDK LIVE adapter: reads + explicitly armed write capability.
No autonomous execution. Writes require separate in-process approval and remain
disabled in current production config.
"""
from pathlib import Path
import json,sys
ROOT=Path(__file__).resolve().parent
VENDOR=ROOT/"vendor"/"weex-connector-python"
for part in ("common/src","clients/contract/src"):
 p=str(VENDOR/part)
 if p not in sys.path:sys.path.insert(0,p)
READ_OPERATIONS=frozenset({"get_capi_v3_account_position_allPosition","get_capi_v3_account_position_singlePosition",
 "get_capi_v3_openOrders","get_capi_v3_order","get_capi_v3_order_history","get_capi_v3_userTrades","get_capi_v3_market_depth"})
WRITE_OPERATIONS=frozenset({"post_capi_v3_order","post_capi_v3_closePositions",
 "post_capi_v3_account_leverage","delete_capi_v3_order","post_capi_v3_placeTpSlOrder","post_capi_v3_modifyTpSlOrder"})
class LiveSdkReadOnly:
 def __init__(self,client=None,*,write_approval=None):
  self._client=client
  self._write_approval=write_approval
 def execute(self,operation,request=None):
  if operation not in READ_OPERATIONS:
   if operation not in WRITE_OPERATIONS:raise PermissionError("UNKNOWN_SDK_OPERATION")
   config=json.loads((ROOT/"weex_ai_risk_config.json").read_text(encoding="utf-8"))
   if config.get("execution",{}).get("enabled") is not True:
    raise PermissionError("LIVE_EXECUTION_DISABLED")
   if self._write_approval is None or self._write_approval(operation,request) is not True:
    raise PermissionError("LIVE_WRITE_APPROVAL_REQUIRED")
  if self._client is None:
   from weex_contract_sdk import Contract
   self._client=Contract.from_env()
  return self._client.rest_api.execute_operation(operation,request or {})
 def capabilities(self):
  from weex_contract_sdk.rest_api.operations import OPERATIONS
  names=set(OPERATIONS)
  return {"readOperations":sorted(READ_OPERATIONS),"availableWriteOperations":sorted(WRITE_OPERATIONS),
   "writeOperationsEnabled":json.loads((ROOT/"weex_ai_risk_config.json").read_text(encoding="utf-8"))["execution"]["enabled"],
   "allReadOpsImplementedInSdk":READ_OPERATIONS.issubset(names),
   "allWriteOpsImplementedInSdk":WRITE_OPERATIONS.issubset(names)}
