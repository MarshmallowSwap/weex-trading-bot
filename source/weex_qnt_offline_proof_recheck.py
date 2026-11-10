"""Independent offline validation of previously recorded QNT live TP proof.

Never touches remote API or writes lifecycle. A PASS certifies a historical
closure, not live readiness or the +15 USDT target.
"""
import json,hashlib
from pathlib import Path
from weex_close_proof import prove,verify_bot_exit
from weex_lifecycle import Lifecycle
ROOT=Path(__file__).resolve().parent
TID='wxentry_7f327b721a398e3e86033c73'
def check():
 engine=Lifecycle(ROOT/'weex_user_live_lifecycle.sqlite3',None,lambda:{})
 item=engine.get(TID)
 folder=ROOT/'weex_reconcile_details'
 target=folder/(hashlib.sha256(TID.encode()).hexdigest()+'.json')
 if not target.exists():return {'state':'NO_PERSISTED_EVIDENCE'}
 data=json.loads(target.read_text(encoding='utf-8'))
 orders=data['orders'];fills=data['fills'];algos=data['algos']
 if data.get('tradeId')!=TID or data.get('symbol')!='QNTUSDT':
  return {'state':'SCOPE_MISMATCH'}
 ack=engine.writes(TID).get('TP',{}).get('response') or []
 if not isinstance(ack,list) or len(ack)!=1 or ack[0].get('success') is not True:
  return {'state':'TP_ACK_NOT_VERIFIED'}
 algo_id=str(ack[0]['orderId'])
 match=[a for a in algos if str(a.get('algoId'))==algo_id]
 if len(match)!=1:return {'state':'ALGO_NOT_UNIQUE'}
 actual_id=str(match[0].get('actualOrderId') or match[0]['algoId'])
 matching_orders=[o for o in orders if str(o.get('orderId'))==actual_id]
 if len(matching_orders)!=1:return {'state':'EXIT_ORDER_NOT_UNIQUE'}
 try:
  verified_id=verify_bot_exit(item,match[0],matching_orders[0],algo_id)
  proof=prove(item,orders,fills,[verified_id])
  if proof.get('evidenceSha256')!=data['proof']['evidenceSha256']:
   raise ValueError('PROOF_DIGEST_CHANGED')
  if proof.get('botTPUsed') is not True or proof.get('resolution')!='CLOSED_BOT_TP_VERIFIED':
   raise ValueError('NOT_BOT_TP')
  return {'state':'HISTORICAL_BOT_TP_PROOF_REVALIDATED','symbol':item['symbol'],
    'quantity':proof['quantity'],'netBeforeFundingUSDT':proof['realizedNetBeforeFundingUSDT'],
    'targetMetBeforeFunding':proof['targetMetBeforeFunding'],
    'proofSha256':proof['evidenceSha256'],
    'currentLifecycleState':item['state'],'canDispatchLive':False,
    'ledgerUpdated':False,'liveWrites':0}
 except Exception as exc:
  return {'state':'PROOF_NOT_REVALIDATED','errorType':type(exc).__name__,
          'reason':str(exc) if isinstance(exc,ValueError) else None,'liveWrites':0}
if __name__=='__main__':print(json.dumps(check()))
