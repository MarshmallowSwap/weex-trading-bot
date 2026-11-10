"""Authenticated GET-only inventory of previously executed reduce-only exits.

No attribution to the proposed pilot or proof of emergency exit capability.
"""
import json
from pathlib import Path
from datetime import datetime,timezone
from decimal import Decimal,InvalidOperation
from monitor import query
from weex_order_pagination import history
from weex_quote_semantics_readonly_probe import check as economic
import live_control
R=Path(__file__).resolve().parent

def run():
 if live_control.state(R)['mode']!='STOPPED':raise PermissionError('LIVE_NOT_STOPPED')
 h=history(max_pages=5)
 if not h['completeWithinRequestedBounds']:raise ValueError('HISTORY_INCOMPLETE')
 found=[]
 for item in h['orders']:
  if item.get('reduceOnly') is not True or str(item.get('status')).upper()!='FILLED':
   continue
  oid=str(item.get('orderId') or '')
  if not oid:continue
  actual=query('/capi/v3/order?orderId='+oid)
  if not isinstance(actual,dict) or str(actual.get('orderId'))!=oid:
   raise ValueError('EXACT_ORDER_READ_FAILED')
  if actual.get('reduceOnly') is not True or str(actual.get('status')).upper()!='FILLED':
   continue
  symbol=actual.get('symbol')
  if not symbol:raise ValueError('MISSING_SYMBOL')
  fills=query('/capi/v3/userTrades?symbol='+symbol+'&orderId='+oid+'&limit=100')
  if not isinstance(fills,list) or len(fills)>=100:raise ValueError('FILLS_NOT_BOUNDED')
  try:
   executed=Decimal(str(actual['executedQty']))
   qty=sum((Decimal(str(f['qty'])) for f in fills),Decimal(0))
   identity=(bool(fills) and executed>0 and qty==executed and
    len({str(f['id']) for f in fills})==len(fills) and
    all(str(f.get('orderId'))==oid for f in fills))
  except (KeyError,ValueError,InvalidOperation,TypeError):
   identity=False
  found.append({'orderId':oid,'symbol':symbol,'kind':actual.get('type'),
                'positionSide':actual.get('positionSide'),
                'fillCount':len(fills),'reduceOnlyObserved':True,
                'fillIdentityVerified':identity,
                'economicState':economic(actual,fills)['state'] if identity else 'INCOMPLETE'})
 return {'checkedAt':datetime.now(timezone.utc).isoformat(),
         'historyOrders':len(h['orders']),'verifiedReduceOnlyClosures':sum(x['fillIdentityVerified'] for x in found),
         'observedReduceOnly':found,'pilotCloseCertified':False,
         'noEmergencyExitProof':True,'exchangeWrites':0}
if __name__=='__main__':
 r=run()
 p=R/'weex_historical_reduceonly_evidence_latest.json';p.write_text(json.dumps(r,indent=2)+'\n')
 print(json.dumps(r))
