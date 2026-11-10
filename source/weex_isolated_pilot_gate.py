"""Isolated ETHUSDT 1x pilot: read-only preflight, never authorizes an order."""
from decimal import Decimal as D,ROUND_DOWN
from pathlib import Path
import json
from weex_live_worker import Reader,public
from weex_margin_sizing import contract_rules
from orderbook_liquidity import inspect as inspect_book
import live_control
ROOT=Path(__file__).resolve().parent

def assess(*,pilot,account_config,positions,orders,algos,metadata,book,mode,integrity_errors,live_gate,
           available_usdt):
 issues=[]
 if mode!='STOPPED':issues.append('BOT_NOT_STOPPED')
 if integrity_errors:issues.append('CODE_INTEGRITY_FAILED')
 if pilot.get('executionEnabled') is not False or pilot.get('liveOrderSubmissionAllowed') is not False:
  issues.append('PILOT_EXECUTION_MUST_BE_DISABLED')
 if pilot.get('marginMode')!='ISOLATED' or pilot.get('leverage')!=1 or pilot.get('maxNewOrders')!=1:
  issues.append('PILOT_SCOPE_INVALID')
 if account_config.get('symbol')!='ETHUSDT' or account_config.get('marginType')!='ISOLATED':
  issues.append('NOT_ISOLATED_ETH')
 if account_config.get('separatedType')!='COMBINED':issues.append('POSITION_MODE_UNEXPECTED')
 if any(str(account_config.get(key))!='1' for key in ('isolatedLongLeverage','isolatedShortLeverage')):
  issues.append('LEVERAGE_NOT_1X')
 if not all(isinstance(x,list) for x in (positions,orders,algos)) or positions or orders or algos:
  issues.append('EXISTING_EXPOSURE_OR_INCOMPLETE')
 if book.get('status')!='OK' or book.get('depthUnitVerified') is not True:
  issues.append('LIVE_ORDERBOOK_NOT_VERIFIED')
 try:
  rules=contract_rules(metadata)
  ask=D(str(book['bestAsk']))
  fee=D(str(pilot['maxAdditionalNotionalUSDT']))
  available=D(str(available_usdt))
  if not ask.is_finite() or ask<=0 or not fee.is_finite() or fee>5 or fee<=0:
   raise ValueError('BAD_SIZING')
  qty=(fee/ask/rules['quantityStep']).to_integral_value(rounding=ROUND_DOWN)*rules['quantityStep']
  if qty<rules['minQuantity'] or qty>rules['maxQuantity']:issues.append('QUANTITY_OUTSIDE_EXCHANGE_LIMITS')
  if available<fee:issues.append('INSUFFICIENT_AVAILABLE_BALANCE')
  indicative={'quantity':str(qty),'ask':str(ask),'notionalUSDT':str(qty*ask),
              'quantityStep':str(rules['quantityStep']),'tick':str(rules['priceTick'])}
 except (KeyError,TypeError,ValueError,ArithmeticError):
  indicative=None;issues.append('INCOMPLETE_SIZING')
 if live_gate.get('gate')!='GO':issues.append('INDEPENDENT_GATE_NO_GO')
 if live_gate.get('checks',{}).get('crash_restart_recovery_live_tested') is not True:
  issues.append('LIVE_CRASH_RESTART_NOT_CERTIFIED')
 # A stop is needed to constrain losses within pilot intent; no SL is currently configured.
 if pilot.get('stopLossVerified') is not True:issues.append('PILOT_STOP_LOSS_NOT_VERIFIED')
 if pilot.get('reduceOnlyCloseVerified') is not True:issues.append('REDUCE_ONLY_EXIT_NOT_VERIFIED')
 return {'scope':'ETHUSDT_ISOLATED_1X_READ_ONLY','checksPassed':not issues,
         'orderAuthorized':False,'issues':sorted(set(issues)),
         'indicativeOrder':indicative,'exchangeWrites':0}

def read():
 if live_control.state(ROOT)['mode']!='STOPPED':raise PermissionError('NOT_STOPPED')
 pilot=json.loads((ROOT/'weex_live_1x_pilot_config.json').read_text(encoding='utf-8'))
 gate=json.loads((ROOT/'live_release_gate_latest.json').read_text(encoding='utf-8'))
 r=Reader(ROOT)
 pos,orders,algos=r.account()
 arr=r.read('get_capi_v3_account_symbolConfig',symbol='ETHUSDT')
 balance=r.read('get_capi_v3_account_balance')
 if len(arr)!=1:raise ValueError('ACCOUNT_CONFIG_AMBIGUOUS')
 usd=next((b['availableBalance'] for b in balance if b.get('asset')=='USDT'),None)
 if usd is None:raise ValueError('USDT_NOT_AVAILABLE')
 metadata=public('/capi/v3/market/exchangeInfo',symbol='ETHUSDT')['symbols'][0]
 book=inspect_book('ETHUSDT')
 return assess(pilot=pilot,account_config=arr[0],positions=pos,orders=orders,algos=algos,
  metadata=metadata,book=book,mode=live_control.state(ROOT)['mode'],
  integrity_errors=live_control.build_errors(ROOT),live_gate=gate,available_usdt=usd)
if __name__=='__main__':
 print(json.dumps(read(),ensure_ascii=False))
