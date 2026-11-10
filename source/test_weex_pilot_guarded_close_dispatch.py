import tempfile,unittest
from pathlib import Path
from weex_isolated_pilot_offline_journal import reserve,connect
from weex_pilot_guarded_close_dispatch import dispatch_close
from contextlib import closing
import json

class FakeClose:
 pilot_live_close_only=True
 def __init__(self,crash=False): self.count=0;self.crash=crash
 def send_close_only(self,op,p):
  self.count+=1
  if self.crash:raise TimeoutError('unknown outcome')
  return {'success':True,'orderId':'SIM_ACK'}

def setup(db):
 reserve(db,pilot_id='P1',side='LONG',quantity='.002',stop_price='2100')
 with closing(connect(db)) as c:
  row=c.execute('SELECT entry_id,close_id,proposals FROM pilot_v1').fetchone()
  c.execute("UPDATE pilot_v1 SET state='ENTRY_RECONCILED_EXTERNALLY'")
  c.commit()
 entry_id,close_id,raw=row
 p=json.loads(raw)['close']
 return {'prepared':True,'canSend':False,'payload':p},{'owned':True,'clientOrderId':entry_id,'quantity':'0.002','positionId':'POS1'}

class GuardedClose(unittest.TestCase):
 def test_ack_still_unreconciled_and_never_retry(self):
  with tempfile.TemporaryDirectory() as t:
   db=Path(t)/'pilot.db'
   plan,owned=setup(db);gw=FakeClose()
   r=dispatch_close(db,'P1',plan,ownership=owned,account_fresh=True,transport=gw)
   self.assertEqual(r['state'],'ACK_RECEIVED_UNRECONCILED')
   self.assertFalse(r['ordersConfirmed'])
   r=dispatch_close(db,'P1',plan,ownership=owned,account_fresh=True,transport=gw)
   self.assertEqual(r['state'],'ALREADY_RESERVED_NO_RETRY')
   self.assertEqual(gw.count,1)
 def test_timeout_is_not_retried(self):
  with tempfile.TemporaryDirectory() as t:
   db=Path(t)/'pilot.db';plan,owned=setup(db);gw=FakeClose(crash=True)
   r=dispatch_close(db,'P1',plan,ownership=owned,account_fresh=True,transport=gw)
   self.assertEqual(r['state'],'OUTCOME_UNKNOWN')
   r=dispatch_close(db,'P1',plan,ownership=owned,account_fresh=True,transport=gw)
   self.assertEqual(r['state'],'ALREADY_RESERVED_NO_RETRY')
   self.assertEqual(gw.count,1)
 def test_invalid_ownership_denied(self):
  with tempfile.TemporaryDirectory() as t:
   db=Path(t)/'pilot.db';plan,owned=setup(db)
   with self.assertRaises(PermissionError):
    dispatch_close(db,'P1',plan,ownership={**owned,'owned':False},account_fresh=True,transport=FakeClose())
 def test_wrong_client_denied(self):
  with tempfile.TemporaryDirectory() as t:
   db=Path(t)/'pilot.db';plan,owned=setup(db)
   plan['payload']['newClientOrderId']='wxpilot_another'
   with self.assertRaises(PermissionError):
    dispatch_close(db,'P1',plan,ownership=owned,account_fresh=True,transport=FakeClose())
 def test_no_open_transport_denied(self):
  with tempfile.TemporaryDirectory() as t:
   db=Path(t)/'pilot.db';plan,owned=setup(db)
   with self.assertRaises(PermissionError):
    dispatch_close(db,'P1',plan,ownership=owned,account_fresh=True,transport=object())
 def test_main_running_denied(self):
  with tempfile.TemporaryDirectory() as t:
   db=Path(t)/'pilot.db';plan,owned=setup(db)
   with self.assertRaises(PermissionError):
    dispatch_close(db,'P1',plan,ownership=owned,account_fresh=True,transport=FakeClose(),main_mode='RUNNING')

if __name__=='__main__':unittest.main()
