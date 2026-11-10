"""CROSS-only 1x ETH pilot exchange preflight. GET-only, never trades.

CROSS leverages the account's shared collateral. This report deliberately
refuses an ISOLATED account even if its crossLeverage field is set.
"""
import json,os
from pathlib import Path
from decimal import Decimal as D,InvalidOperation
from datetime import datetime,timezone
from weex_live_worker import Reader
import live_control
ROOT=Path(__file__).resolve().parent
def check(cfg,exchange,positions,regular,algos,mode,integrity):
 reasons=[]
 if mode!='STOPPED':reasons.append('MAIN_BOT_NOT_STOPPED')
 if integrity:reasons.append('MANIFEST_INTEGRITY_ERROR')
 if cfg.get('exchange')!='WEEX' or cfg.get('marginMode')!='CROSS' or cfg.get('leverage')!=1:
  reasons.append('NOT_CROSS_1X_PILOT')
 if cfg.get('executionEnabled') is not False or cfg.get('liveOrderSubmissionAllowed') is not False:
  reasons.append('PILOT_NOT_SAFELY_DISARMED')
 if not isinstance(exchange,dict) or exchange.get('symbol')!='ETHUSDT':
  reasons.append('ETH_ACCOUNT_CONFIG_NOT_VERIFIED')
 elif exchange.get('marginType') not in ('CROSS','CROSSED'):
  reasons.append('EXCHANGE_ETH_NOT_CROSS')
 else:
  try:
   if D(str(exchange.get('crossLeverage')))!=D(1):
    reasons.append('EXCHANGE_CROSS_LEVERAGE_NOT_1X')
  except (InvalidOperation,TypeError,ValueError):
   reasons.append('EXCHANGE_CROSS_LEVERAGE_UNREADABLE')
 if not all(isinstance(v,list) and not v for v in (positions,regular,algos)):
  reasons.append('EXISTING_EXPOSURE_OR_UNKNOWN_ORDERS')
 return {'crossExchangeReady':not reasons,'entryAuthorized':False,
         'mainMode':mode,'pilotMarginMode':cfg.get('marginMode'),
         'exchangeMarginMode':exchange.get('marginType') if isinstance(exchange,dict) else None,
         'exchangeCrossLeverage':exchange.get('crossLeverage') if isinstance(exchange,dict) else None,
         'reasons':reasons,'exchangeWrites':0}

def run():
 cfg=json.loads((ROOT/'weex_live_1x_pilot_config.json').read_text(encoding='utf-8'))
 r=Reader(ROOT)
 values=r.read('get_capi_v3_account_symbolConfig',symbol='ETHUSDT')
 positions,regular,algos=r.account()
 x=check(cfg,values[0] if isinstance(values,list) and len(values)==1 else {},
         positions,regular,algos,live_control.state(ROOT)['mode'],
         live_control.build_errors(ROOT))
 x['checkedAt']=datetime.now(timezone.utc).isoformat()
 path=ROOT/'weex_cross_1x_pilot_exchange_preflight_latest.json'
 tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(x,indent=2)+'\n');os.replace(tmp,path)
 return x
if __name__=='__main__':print(json.dumps(run()))
