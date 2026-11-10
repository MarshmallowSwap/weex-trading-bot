"""Independent production GET-only proof of the exact CROSS 1x test.
Never writes to WEEX; validates entry/exit IDs, fills, stop terminal status,
and a flat account. Computes realized trade cashflow from child fills only.
"""
import json,os
from pathlib import Path
from decimal import Decimal as D
from datetime import datetime,timezone
from weex_live_worker import Reader
import live_control
ROOT=Path(__file__).resolve().parent
SOURCE=ROOT/'weex_cross_one_shot_real_pilot_20261109.json'
OUTPUT=ROOT/'weex_cross_one_shot_real_independent_audit_20261109.json'
trial=json.loads(SOURCE.read_text(encoding='utf-8'))
if trial.get('stage')!='CROSS_PILOT_CLOSED_AND_VERIFIED' or trial.get('host')!='https://api-contract.weex.com':
 raise PermissionError('TRIAL_NOT_COMPLETED')
if live_control.state(ROOT)['mode']!='STOPPED':raise PermissionError('MAIN_NOT_STOPPED')
reader=Reader(ROOT)
entry=reader.read('get_capi_v3_order',orderId=trial['entryOrderId'])
close=reader.read('get_capi_v3_order',orderId=trial['closeOrderId'])
entries=reader.read('get_capi_v3_userTrades',symbol='ETHUSDT',orderId=trial['entryOrderId'],limit=100)
exits=reader.read('get_capi_v3_userTrades',symbol='ETHUSDT',orderId=trial['closeOrderId'],limit=100)
positions,regular,algos=reader.account()
history=reader.read('get_capi_v3_allAlgoOrders',symbol='ETHUSDT')
cfg=reader.read('get_capi_v3_account_symbolConfig',symbol='ETHUSDT')
q=D('.002')
def exact_fills(rows,orderid,side):
 return (isinstance(rows,list) and 0<len(rows)<100 and
   len({str(f.get('id')) for f in rows})==len(rows) and
   all(str(f.get('orderId'))==orderid and f.get('symbol')=='ETHUSDT'
    and f.get('side')==side and f.get('positionSide')=='LONG' for f in rows)
   and sum((D(str(f['qty'])) for f in rows),D(0))==q)
entry_ok=(isinstance(entry,dict) and str(entry.get('orderId'))==trial['entryOrderId']
 and entry.get('clientOrderId')==trial['clientOrderId'] and entry.get('status')=='FILLED'
 and entry.get('symbol')=='ETHUSDT' and entry.get('side')=='BUY'
 and D(str(entry.get('executedQty','0')))==q and
 entry.get('positionSide')=='LONG' and exact_fills(entries,trial['entryOrderId'],'BUY'))
close_ok=(isinstance(close,dict) and str(close.get('orderId'))==trial['closeOrderId']
 and close.get('status')=='FILLED' and close.get('reduceOnly') is True
 and close.get('symbol')=='ETHUSDT' and close.get('side')=='SELL'
 and D(str(close.get('executedQty','0')))==q and
 close.get('positionSide')=='LONG' and exact_fills(exits,trial['closeOrderId'],'SELL'))
stop_rows=[x for x in history.get('orders',[]) if isinstance(x,dict)
  and str(x.get('algoId'))==trial['stopAlgoId']] if isinstance(history,dict) else []
stop_ok=len(stop_rows)==1 and stop_rows[0].get('algoStatus') in ('CANCELED','CANCELLED')
flat=positions==[] and regular==[] and algos==[]
cross_ok=isinstance(cfg,list) and len(cfg)==1 and cfg[0].get('marginType') in ('CROSSED','CROSS') and str(cfg[0].get('crossLeverage'))=='1'
def sums(rows):
 notional=sum((D(str(f['quoteQty'])) for f in rows),D(0))
 fees=sum((D(str(f.get('commission','0'))) for f in rows),D(0))
 return str(notional),str(fees)
enter_value,enter_fee=sums(entries) if isinstance(entries,list) else ('0','0')
exit_value,exit_fee=sums(exits) if isinstance(exits,list) else ('0','0')
fee_assets=sorted({str(x.get('commissionAsset')) for x in (entries+exits) if isinstance(x,dict)}) if isinstance(entries,list) and isinstance(exits,list) else []
report={'checkedAt':datetime.now(timezone.utc).isoformat(),
 'environment':'WEEX_REAL_ACCOUNT','symbol':'ETHUSDT','expectedMargin':'CROSS','expectedLeverage':1,
 'entryOrderId':trial['entryOrderId'],'closeOrderId':trial['closeOrderId'],'stopAlgoId':trial['stopAlgoId'],
 'entryVerified':entry_ok,'reduceOnlyCloseVerified':close_ok,'stopTerminalVerified':stop_ok,
 'stopStatus':stop_rows[0].get('algoStatus') if len(stop_rows)==1 else None,
 'accountFlatVerified':flat,'cross1xStillConfigured':cross_ok,
 'entryFillCount':len(entries) if isinstance(entries,list) else None,
 'closeFillCount':len(exits) if isinstance(exits,list) else None,
 'entryQuoteUSDT':enter_value,'exitQuoteUSDT':exit_value,
 'entryReportedCommission':enter_fee,'exitReportedCommission':exit_fee,
 'commissionAssets':fee_assets,
 'grossPriceDifferenceUSDT':str(D(exit_value)-D(enter_value)),
 'exchangeWrites':0,'botMode':live_control.state(ROOT)['mode'],
 'allIndependentChecksPassed':all((entry_ok,close_ok,stop_ok,flat,cross_ok))}
tmp=OUTPUT.with_suffix('.tmp');tmp.write_text(json.dumps(report,indent=2));os.replace(tmp,OUTPUT)
print(json.dumps(report))
