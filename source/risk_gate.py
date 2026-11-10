"""WEEX pretrade risk gate; deterministic and fail-closed. Does not submit orders."""
from decimal import Decimal,InvalidOperation
D=lambda v:Decimal(str(v))
def evaluate(candidate,config):
 reasons=[]
 def num(key):
  try:
   v=D(candidate[key])
   if not v.is_finite() or v<=0:raise ValueError(key)
   return v
  except (KeyError,InvalidOperation,ValueError,TypeError):
   reasons.append("INVALID_"+key.upper());return None
 margin=num("marginUSDT");leverage=num("leverage");maxlev=num("accountMaxLeverage")
 if candidate.get("marketDataStatus")!="FRESH":reasons.append("MARKET_DATA_NOT_FRESH")
 if candidate.get("bookDepthUnitVerified") is not True:reasons.append("BOOK_UNITS_NOT_VERIFIED")
 if candidate.get("executionCostsVerified") is not True:reasons.append("COSTS_NOT_VERIFIED")
 if candidate.get("positionReconciled") is not True:reasons.append("POSITION_NOT_RECONCILED")
 if candidate.get("side") not in ("LONG","SHORT"):reasons.append("INVALID_SIDE")
 if leverage and maxlev and leverage>maxlev:reasons.append("ABOVE_ACCOUNT_LEVERAGE")
 if margin and margin!=D(config["risk"]["initialMarginTargetUSDT"]):reasons.append("MARGIN_MISMATCH")
 current=candidate.get("openPositionCount")
 limit=config["telegramSettings"]["maxConcurrentPositions"]["default"]
 if type(current) is not int or current<0 or current>=limit:reasons.append("POSITION_LIMIT")
 if config.get("execution",{}).get("enabled") is not True:reasons.append("LIVE_DISABLED")
 return {"approved":not reasons,"reasons":reasons,"noOrderSubmitted":True}
