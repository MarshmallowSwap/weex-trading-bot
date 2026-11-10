"""Durable exact one-shot test permission candidate. Not connected to HTTP transport.

This file cannot grant the production live switch, bypass release validation,
submit orders, or alter certification evidence. Approval is an external boolean;
the one-shot reservation is consumed before any hypothetical dispatch.
"""
import json,sqlite3,hashlib,time
from pathlib import Path
from contextlib import closing
from decimal import Decimal as D
from weex_supervised_crash_executor_v2 import CLIENT_ID,SYMBOL

class Denied(PermissionError):pass

def exact_payload(payload):
 if not isinstance(payload,dict) or set(payload)!={'symbol','side','positionSide','type','quantity',
  'newClientOrderId','slTriggerPrice','SlWorkingType'}:
  raise Denied('ENTRY_FIELDS_NOT_EXACT')
 if (payload['symbol']!=SYMBOL or payload['side']!='BUY' or payload['positionSide']!='LONG'
   or payload['type']!='MARKET' or payload['newClientOrderId']!=CLIENT_ID
   or payload['SlWorkingType']!='MARK_PRICE' or D(str(payload['quantity']))!=D('.001')):
  raise Denied('ENTRY_NOT_ONE_SHOT_SCOPE')
 stop=D(str(payload['slTriggerPrice']))
 if not stop.is_finite() or stop<=0:raise Denied('INVALID_STOP')
 return json.dumps(payload,sort_keys=True,separators=(',',':'))

def authorize_once(dbpath,payload,*,approval,context):
 """Persist a single irreversible reservation; cannot return HTTP credentials."""
 raw=exact_payload(payload)
 if approval is not True:raise Denied('EXPLICIT_APPROVAL_REQUIRED')
 if not isinstance(context,dict):raise Denied('FRESH_CONTEXT_REQUIRED')
 if (context.get('mainMode')!='STOPPED' or context.get('productionIntegrity') is not True
     or context.get('accountFlat') is not True or context.get('accountLeverage')!='100'
     or context.get('atomicStopVerified') is not True or context.get('closePathValidated') is not True
     or context.get('independentSupervisorReady') is not True
     or context.get('apiBudgetReady') is not True):
  raise Denied('PRE_EXECUTION_GATES_NOT_ALL_PASSED')
 if (type(context.get('observedAtMs')) is not int or
   not 0<=int(time.time()*1000)-context['observedAtMs']<=5000):
  raise Denied('STALE_PRE_EXECUTION_CONTEXT')
 path=Path(dbpath)
 with closing(sqlite3.connect(path,timeout=8)) as c:
  c.execute('PRAGMA busy_timeout=8000')
  c.execute('CREATE TABLE IF NOT EXISTS permit (id TEXT PRIMARY KEY,sha TEXT,status TEXT,created REAL)')
  c.execute('BEGIN IMMEDIATE')
  digest=hashlib.sha256(raw.encode()).hexdigest()
  if c.execute('SELECT 1 FROM permit WHERE id=?',(CLIENT_ID,)).fetchone():
   c.rollback();raise Denied('ONE_SHOT_ALREADY_CONSUMED')
  c.execute('INSERT INTO permit VALUES(?,?,?,?)',(CLIENT_ID,digest,'RESERVED_NO_RETRY',time.time()))
  c.commit()
 return {'status':'RESERVED_NO_RETRY','clientOrderId':CLIENT_ID,
  'payloadSha256':digest,'exchangeWrites':0,'dispatchAllowed':False,
  'productionReleaseBypassed':False}

if __name__=='__main__':
 print(json.dumps({'status':'ONE_SHOT_PERMISSION_POLICY_OFFLINE',
  'integratedWithProductionGateway':False,'exchangeWrites':0}))
