"""Fail-closed WEEX isolated pilot transport harness: simulations only.

No network client, real credentials, or live write method. A caller must supply
an explicitly marked simulation gateway. An uncertain outcome cannot be retried.
"""
import json
from contextlib import closing
from weex_isolated_pilot_offline_journal import connect

OPERATIONS={'entry':'post_capi_v3_order','stop':'post_capi_v3_placeTpSlOrder',
            'close':'post_capi_v3_order'}
STATES={'entry':'PREPARED_NO_SEND','stop':'ENTRY_RECONCILED_EXTERNALLY',
        'close':'STOP_RECONCILED_EXTERNALLY'}
def schema(c):
 c.execute("""CREATE TABLE IF NOT EXISTS pilot_dispatch_v1(
 pilot_id TEXT NOT NULL, stage TEXT NOT NULL, status TEXT NOT NULL,
 result TEXT, PRIMARY KEY(pilot_id,stage))""")
def simulate_dispatch(db,pilot_id,stage,gateway):
 if stage not in OPERATIONS:raise ValueError('UNKNOWN_STAGE')
 if gateway is None or getattr(gateway,'simulation_only',False) is not True:
  raise PermissionError('SIMULATOR_REQUIRED')
 with closing(connect(db)) as c:
  schema(c);c.execute('BEGIN IMMEDIATE')
  row=c.execute('SELECT state,proposals FROM pilot_v1 WHERE pilot_id=?',(pilot_id,)).fetchone()
  if row is None:
   c.rollback();raise ValueError('UNKNOWN_PILOT')
  prior=c.execute('SELECT status FROM pilot_dispatch_v1 WHERE pilot_id=? AND stage=?',
                   (pilot_id,stage)).fetchone()
  if prior:
   c.rollback()
   return {'state':'ALREADY_HANDLED_NO_RETRY','previous':prior[0],'sentRealOrders':False}
  if row[0]!=STATES[stage]:
   c.rollback()
   return {'state':'PREREQUISITE_NOT_CERTIFIED','sentRealOrders':False}
  payload=json.loads(row[1])[stage]
  c.execute('INSERT INTO pilot_dispatch_v1 VALUES(?,?,?,NULL)',
            (pilot_id,stage,'SIMULATION_OUTCOME_UNKNOWN'))
  c.commit()
 try:
  ack=gateway.simulate(OPERATIONS[stage],payload)
  if not isinstance(ack,dict) or ack.get('success') is not True or not ack.get('orderId'):
   raise ValueError('SIMULATED_ACK_INCOMPLETE')
 except Exception as error:
  return {'state':'SIMULATION_OUTCOME_UNKNOWN','errorClass':type(error).__name__,
          'retryAllowed':False,'sentRealOrders':False}
 with closing(connect(db)) as c:
  schema(c)
  with c:
   c.execute('UPDATE pilot_dispatch_v1 SET status=?,result=? WHERE pilot_id=? AND stage=?',
             ('SIMULATED_ACK_ONLY',json.dumps({'orderId':str(ack['orderId'])}),pilot_id,stage))
 return {'state':'SIMULATED_ACK_ONLY','exchangeAccepted':False,
         'nextStageAuthorized':False,'sentRealOrders':False}
