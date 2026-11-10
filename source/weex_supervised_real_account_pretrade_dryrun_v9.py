"""Production pilot full plan/guard dry run. Authenticated GETs only; no order POST.

Isolates Lifecycle SQLite in temporary directory. A local mock readiness flag is
used solely to evaluate code beyond the production readiness check: this script
NEVER invokes run_child, Gateway.write, send_once, grants or live_control changes.
"""
from __future__ import annotations
import json,tempfile
from pathlib import Path
from unittest.mock import patch
from weex_supervised_crash_entry_child_v5 import fresh_capture,PilotGateway,ROOT
from weex_live_worker import Lifecycle,SCOPE
def run():
 results={'status':'OFFLINE_REAL_ACCOUNT_PRETRADE_CHECK','liveReleaseCertified':False,
          'liveEntryAuthorized':False,'realOrderPosts':0,'sqliteProductionWrites':0}
 try:
  import live_control
  if live_control.state(ROOT)['mode']!='STOPPED' or live_control.build_errors(ROOT):
   return {**results,'status':'BLOCKED_PRODUCTION_MODE_OR_BUILD'}
  # Only bypasses supervisor readiness in THIS read-only validation process,
  # never reaches any permit creation or HTTP POST.
  with patch('weex_supervised_crash_entry_child_v5.supervisor_ready',return_value=True):
   plan,ctx,config,payload,reader=fresh_capture(ROOT)
  results.update(freshCapture='PASS',symbol=payload.get('symbol'),
                 quantity=payload.get('quantity'),stop=payload.get('slTriggerPrice'),
                 entryOrderFields=sorted(payload),requestedLeverage=plan.get('requestedLeverage'))
  with tempfile.TemporaryDirectory(prefix='weex-entry-readonly-plan-') as td:
   sandbox=dict(config)
   sandbox['execution']=dict(config['execution'],enabled=True,mode='LIVE')
   gateway=PilotGateway(ROOT,reader,ctx)
   engine=Lifecycle(Path(td)/'test_guard.sqlite3',gateway,lambda:sandbox)
   gateway.engine=engine
   from weex_supervised_crash_executor_v2 import SIGNAL_ID,CLIENT_ID
   item=engine.prepare(SIGNAL_ID,plan)
   gateway.current=item['id']
   results['preparedIdMatch']=(item['id']==CLIENT_ID)
   results['preparedPayloadMatch']=(item['plan']['entry']==payload)
   if not results['preparedIdMatch'] or not results['preparedPayloadMatch']:
    return {**results,'status':'IMMUTABLE_PLAN_MISMATCH'}
   engine.guard(item,ctx)
   results['productionLifecycleGuard']='PASS'
  return {**results,'status':'PRODUCTION_PRETRADE_DRYRUN_GUARD_PASS'}
 except Exception as exc:
  from weex_supervised_crash_executor_v2 import Blocked
  return {**results,'status':'PRETRADE_GUARD_BLOCKED',
          'failureType':type(exc).__name__,
          'reason':str(exc) if type(exc) in (ValueError,PermissionError,KeyError,Blocked) else type(exc).__name__}
if __name__=='__main__':
 print(json.dumps(run(),ensure_ascii=False))
