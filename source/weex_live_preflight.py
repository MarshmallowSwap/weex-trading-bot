"""WEEX LIVE pre-submit freshness, quote cap and post-submit evidence checks.
These routines make no trading API calls. No production config changes.
"""
from datetime import datetime,timezone
from decimal import Decimal,InvalidOperation
from weex_live_entry_with_tp import build_order
def fresh_order(*,symbol,side,quantity,tp_price,client_order_id,quote,now_ms=None):
 now_ms=int(datetime.now(timezone.utc).timestamp()*1000) if now_ms is None else int(now_ms)
 if not isinstance(quote,dict):raise ValueError("MISSING_QUOTE")
 if quote.get("symbol")!=symbol:raise ValueError("QUOTE_SYMBOL_MISMATCH")
 stamp=int(quote["timestampMs"])
 if stamp>now_ms+1000 or now_ms-stamp>5000:raise ValueError("STALE_QUOTE")
 bid=Decimal(str(quote["bid"]));ask=Decimal(str(quote["ask"]))
 if not bid.is_finite() or not ask.is_finite() or bid<=0 or ask<=bid:raise ValueError("INVALID_BID_ASK")
 # Worst-case slippage allowance: even a market buy up to 0.5% above ask may not exceed 5 USDT.
 ref=ask if side=="LONG" else bid
 worst=ref*Decimal("1.005")
 if Decimal(str(quantity))*worst>Decimal("5"):raise ValueError("NOTIONAL_WITH_SLIPPAGE_EXCEEDS_LIMIT")
 if (ask-bid)/bid>Decimal("0.003"):raise ValueError("SPREAD_TOO_WIDE")
 return build_order(symbol=symbol,side=side,quantity=quantity,price=worst,
    tp_price=tp_price,client_order_id=client_order_id)
def verify_after_submit(*,client_order_id,ack,orders,positions,tp_orders,intent=None,
                        trades=None,before_positions=None,expected_tp_id=None,
                        snapshot_complete=False,snapshot_age_ms=None):
 """Match actual V3 schemas without inventing position.entryOrderId.

 TP identity must come from an acknowledged TP submission/journal. Matching only
 symbol/price is not ownership. This observation never authorizes another write.
 """
 def result(state,reason,**values):
  return {'state':state,'reason':reason,'canSubmit':False,'canClose':False,**values}
 if isinstance(ack,dict) and ack.get('success') is False:
  return result('ORDER_REJECTED','EXCHANGE_REJECTED_REQUEST')
 if not isinstance(ack,dict) or not ack.get('orderId'):
  return result('UNKNOWN_EXECUTION','NO_CONFIRMED_ACK')
 if ack.get('success') is not True or ack.get('clientOrderId')!=client_order_id:
  return result('RECONCILIATION_REQUIRED','ACK_NOT_BOUND_TO_CLIENT')
 if snapshot_complete is not True or not isinstance(snapshot_age_ms,(int,float)) or not 0<=snapshot_age_ms<=5000:
  return result('RECONCILIATION_REQUIRED','INCOMPLETE_OR_STALE_SNAPSHOT')
 if not isinstance(intent,dict) or not all(isinstance(rows,list) and all(isinstance(row,dict) for row in rows) for rows in (orders,positions,tp_orders,trades,before_positions)):
  return result('RECONCILIATION_REQUIRED','MISSING_EVIDENCE')
 symbol=intent.get('symbol');side=intent.get('positionSide')
 if not symbol or side not in ('LONG','SHORT') or intent.get('newClientOrderId')!=client_order_id:
  return result('RECONCILIATION_REQUIRED','INTENT_MISMATCH')
 entry_side='BUY' if side=='LONG' else 'SELL'
 if intent.get('side')!=entry_side:
  return result('RECONCILIATION_REQUIRED','INTENT_SIDE_MISMATCH')
 order_id=str(ack['orderId'])
 observed=[o for o in orders if str(o.get('orderId'))==order_id or o.get('clientOrderId')==client_order_id]
 if len(observed)!=1:return result('RECONCILIATION_REQUIRED','ORDER_NOT_UNIQUELY_MATCHED')
 order=observed[0]
 if (str(order.get('orderId'))!=order_id or order.get('clientOrderId')!=client_order_id
     or order.get('symbol')!=symbol or order.get('positionSide')!=side or order.get('side')!=entry_side):
  return result('RECONCILIATION_REQUIRED','ORDER_INTENT_MISMATCH')
 if any(p.get('symbol')==symbol for p in before_positions):
  return result('RECONCILIATION_REQUIRED','PREEXISTING_SYMBOL_EXPOSURE')
 if any(o.get('symbol')==symbol and str(o.get('orderId'))!=order_id for o in orders):
  return result('RECONCILIATION_REQUIRED','OTHER_SYMBOL_ACTIVITY')
 try:
  qty=Decimal(str(intent['quantity']));filled=Decimal(str(order['executedQty']))
  if not qty.is_finite() or qty<=0 or not filled.is_finite() or filled<0 or filled>qty:raise ValueError()
  if order.get('status')!='FILLED' or filled!=qty:
   return result('RECONCILIATION_REQUIRED','ORDER_NOT_FULLY_FILLED',filledQty=str(filled))
  total=Decimal(0);seen=set()
  for trade in trades:
   if trade.get('symbol')!=symbol and str(trade.get('orderId'))!=order_id:continue
   if (str(trade.get('orderId'))!=order_id or trade.get('symbol')!=symbol
       or trade.get('positionSide')!=side or trade.get('side')!=entry_side):
    return result('RECONCILIATION_REQUIRED','OTHER_OR_MISMATCHED_FILL')
   trade_id=str(trade.get('id') or '')
   amount=Decimal(str(trade['qty']))
   if not trade_id or trade_id in seen or not amount.is_finite() or amount<=0:raise ValueError()
   seen.add(trade_id);total+=amount
  if total!=filled or not seen:return result('RECONCILIATION_REQUIRED','FILL_TOTAL_MISMATCH')
  own=[p for p in positions if p.get('symbol')==symbol]
  if len(own)!=1 or own[0].get('side')!=side or not str(own[0].get('id') or '').isdigit():
   return result('RECONCILIATION_REQUIRED','POSITION_NOT_UNIQUELY_MATCHED')
  if Decimal(str(own[0]['size']))!=filled:
   return result('RECONCILIATION_REQUIRED','POSITION_QUANTITY_MISMATCH')
  if not expected_tp_id:
   return result('TP_NOT_CONFIRMED','TP_IDENTITY_NOT_BOUND',orderId=order_id)
  matched=[p for p in tp_orders if str(p.get('algoId'))==str(expected_tp_id)]
  if len(matched)!=1:return result('TP_NOT_CONFIRMED','MISSING_OR_DUPLICATE_TP')
  tp=matched[0]
  if (tp.get('symbol')!=symbol or tp.get('positionSide')!=side
      or tp.get('side')!=('SELL' if side=='LONG' else 'BUY')
      or tp.get('orderType') not in ('TAKE_PROFIT','TAKE_PROFIT_MARKET')
      or tp.get('algoStatus') not in ('NEW','UNTRIGGERED')
      or tp.get('reduceOnly') is not True
      or Decimal(str(tp['quantity']))!=filled
      or Decimal(str(tp['triggerPrice']))!=Decimal(str(intent['tpTriggerPrice']))
      or tp.get('workingType')!=intent.get('TpWorkingType','CONTRACT_PRICE')):
   return result('TP_NOT_CONFIRMED','TP_PARAMETERS_OR_STATUS_MISMATCH')
 except (ValueError,KeyError,TypeError,InvalidOperation):
  return result('RECONCILIATION_REQUIRED','INVALID_NUMERIC_OR_FILL_EVIDENCE')
 return result('OPEN_WITH_MATCHED_TP','READ_ONLY_OBSERVATION',orderId=order_id,
               positionId=str(own[0]['id']),filledQty=str(filled),tpId=str(expected_tp_id))
