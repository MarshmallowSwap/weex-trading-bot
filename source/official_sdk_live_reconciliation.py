"""WEEX official SDK live read-only reconciler with local order integrity audit."""
import json
from pathlib import Path
from datetime import datetime,timezone
from official_weex_live_sdk_adapter import LiveSdkReadOnly
from official_sdk_live_order_audit import audit
from official_sdk_live_bindings import bindings
from live_sdk_reservation_reconcile import inspect as inspect_reservations
from live_sdk_fill_observer import reconcile_fills
from live_sdk_end_to_end_audit import evaluate as evaluate_end_to_end
from weex_common.configuration import ConfigurationRestAPI
from weex_contract_sdk import Contract
R=Path(__file__).resolve().parent
def run():
 c=json.loads((R/"weex_credentials.json").read_text(encoding="utf-8"))
 api=LiveSdkReadOnly(Contract(config_rest_api=ConfigurationRestAPI(
  base_path="https://api-contract.weex.com",api_key=c["api_key"],api_secret=c["secret_key"],
  passphrase=c["passphrase"],max_retries=0,timeout=15)))
 def get(op,request):
  response=api.execute(op,request)
  if response.status_code!=200 or not isinstance(response.data,list):
   raise RuntimeError("INVALID_"+op)
  return response.data
 positions=get("get_capi_v3_account_position_allPosition",{})
 opened=get("get_capi_v3_openOrders",{"query":{"limit":100,"page":0}})
 trades=get("get_capi_v3_userTrades",{"query":{"limit":100}})
 hist=get("get_capi_v3_order_history",{"query":{"limit":100,"page":0}})
 local_bindings=bindings()
 checks=audit(hist+opened,trades,local_bindings)
 reservation_checks=inspect_reservations(hist,opened)
 fill_checks=reconcile_fills(hist+opened,trades,reservation_checks['items'])
 e2e=evaluate_end_to_end(hist,opened,trades,None)
 report={"checkedAt":datetime.now(timezone.utc).isoformat(),"source":"OFFICIAL_WEEX_CONTRACT_SDK",
 "positions":len(positions),"openOrders":len(opened),"executions":len(trades),
 "historyOrders":len(hist),"matchedExecutions":checks["trades"]-checks["unmatchedTradeCount"],
 "duplicateOrderIds":checks["duplicateOrderIds"],"unmatchedTradeCount":checks["unmatchedTradeCount"],
 "localBindingCandidates":len(local_bindings),"botOrderBindingsMatched":checks["botBindingsMatched"],
 "reservationCount":len(reservation_checks["items"]),"unresolvedReservations":sum(x["reconciliation"]!="EXCHANGE_ORDER_OBSERVED" for x in reservation_checks["items"]),
 "reservationSnapshotSafe":reservation_checks["safe"],"fillObservations":fill_checks["observations"],
 "e2eObservation":e2e,
 "canRetryUnknown":False,"botOwnedPositionsVerified":0,
 "writes":False,"liveGo":False,
 "note":"Read-only reconciliation; historic order coverage may be incomplete"}
 p=R/"official_sdk_live_reconciliation_latest.json";tmp=p.with_suffix(".tmp")
 tmp.write_text(json.dumps(report,indent=2),encoding="utf-8");tmp.replace(p)
 return report
if __name__=="__main__":print(json.dumps(run()))
