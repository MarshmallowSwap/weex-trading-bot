"""Narrow real-test dispatch permit separate from production GO.

Only a durably reserved supervised ETHUSDT 100x test may consume this permit,
once, after the true production Lifecycle has persisted an UNKNOWN ENTRY.
Normal production dispatch_permission remains unmodified and mandatory for
all automatic/manual strategy orders. This module cannot directly send HTTP.
"""
import hashlib,json,sqlite3,time
from pathlib import Path
from contextlib import closing
from weex_supervised_one_shot_permission_v4 import exact_payload,CLIENT_ID
from weex_supervised_real_recovery_v3 import prove_unknown_intent
from weex_supervised_crash_executor_v2 import SIGNAL_ID

class DispatchDenied(PermissionError):pass

def check_and_consume(*,root,permit_db,payload):
 root=Path(root);permit_db=Path(permit_db)
 raw=exact_payload(payload)
 if not permit_db.is_file():raise DispatchDenied('MONO_USE_PERMISSION_MISSING')
 import live_control
 cfg=json.loads((root/'weex_ai_risk_config.json').read_text(encoding='utf-8'))
 if live_control.state(root)['mode']!='STOPPED' or live_control.build_errors(root):
  raise DispatchDenied('PRODUCTION_NOT_STOPPED_OR_INTEGRITY_FAILURE')
 if (cfg['execution']['enabled'] is not False or cfg['execution']['mode']!='PRETRADE'
     or cfg['risk']['minimumLeverage']!=100):
  raise DispatchDenied('PRODUCTION_CONFIG_NOT_PRETRADE_100X')
 if payload['newClientOrderId']!=CLIENT_ID:
  raise DispatchDenied('UNEXPECTED_CLIENT_ID')
 real=prove_unknown_intent(root/'weex_user_live_lifecycle.sqlite3',CLIENT_ID)
 if real!=payload:raise DispatchDenied('PRODUCTION_JOURNAL_PAYLOAD_MISMATCH')
 with closing(sqlite3.connect(permit_db,timeout=8)) as c:
  c.execute('PRAGMA busy_timeout=8000')
  c.execute('BEGIN IMMEDIATE')
  row=c.execute('SELECT sha,status,created FROM permit WHERE id=?',(CLIENT_ID,)).fetchone()
  if not row or row[1]!='RESERVED_NO_RETRY':
   c.rollback();raise DispatchDenied('PERMIT_MISSING_OR_ALREADY_CONSUMED')
  if row[0]!=hashlib.sha256(raw.encode()).hexdigest():
   c.rollback();raise DispatchDenied('PERMIT_HASH_MISMATCH')
  if not 0<=time.time()-row[2]<=120:
   c.rollback();raise DispatchDenied('PERMIT_EXPIRED')
  c.execute('UPDATE permit SET status=? WHERE id=?',('DISPATCH_CONSUMED',CLIENT_ID))
  c.commit()
 return {'status':'CONSUMED_BEFORE_NETWORK','orderId':CLIENT_ID,'noRetry':True}
