"""Pure policy classification: distinguish user-disabled SL from unavailable coverage."""
def classify(coverage_result, sl_requested):
 if not coverage_result.get("verified"):
  return {"status":"UNVERIFIED","reason":coverage_result.get("reason","Coverage not certified")}
 if sl_requested is False:
  return {"status":"SL_OFF_BY_CONFIGURATION","reason":"No stop loss requested; liquidation exposure remains"}
 if not coverage_result.get("slCovered"):
  return {"status":"STOP_COVERAGE_GAP","reason":"Stop requested but full stop coverage not verified"}
 return {"status":"COVERAGE_CANDIDATE","reason":"Requires exchange-side trigger/quantity verification"}
