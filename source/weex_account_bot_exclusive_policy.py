"""WEEX main account declared bot-only for new trading activity.

The declaration is operational intent, NOT evidence of exchange permissions,
margin isolation, release readiness, or authorization to place an order.
Existing lifecycle history is retained. Live control stays STOPPED.
"""
from datetime import datetime,timezone
import json,os
from pathlib import Path
from weex_live_worker import Reader,ROOT
from live_control import state
POLICY='weex_account_bot_exclusive_policy.json'
def record(root=ROOT,reader=None):
 root=Path(root)
 if state(root)['mode']!='STOPPED':raise PermissionError('LIVE_MUST_REMAIN_STOPPED')
 p,o,a=(reader or Reader(root)).account()
 if not isinstance(p,list) or not isinstance(o,list) or not isinstance(a,list):
  raise ValueError('INCOMPLETE_ACCOUNT_SNAPSHOT')
 if p or o or a:raise ValueError('ACCOUNT_MUST_BE_FLAT_AND_ORDER_FREE')
 old=root/POLICY
 declaration={'policy':'BOT_EXCLUSIVE_FOR_NEW_TRADES','scope':'CURRENT_WEEX_ACCOUNT',
    'declaredBy':'USER_IN_CHAT','observedAt':datetime.now(timezone.utc).isoformat(),
    'initialPositions':0,'initialRegularOrders':0,'initialConditionalOrders':0,
    'automaticCloseHistoricalManualPositions':False,
    'ownershipProvenByPolicyAlone':False,
    'liveDispatchEnabled':False,'canChangeRiskConfiguration':False,
    'previousLifecycleRecordsPreserved':True}
 if old.exists():
  existing=json.loads(old.read_text(encoding='utf-8'))
  if existing.get('policy')!=declaration['policy'] or existing.get('scope')!=declaration['scope']:
   raise ValueError('DIFFERENT_POLICY_ALREADY_EXISTS')
  return {'state':'POLICY_ALREADY_RECORDED','liveMode':'STOPPED','liveWrites':0}
 tmp=old.with_suffix('.tmp')
 tmp.write_text(json.dumps(declaration,indent=2),encoding='utf-8')
 os.replace(tmp,old)
 return {'state':'POLICY_RECORDED','liveMode':'STOPPED','liveWrites':0}
if __name__=='__main__':print(json.dumps(record()))
