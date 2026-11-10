"""Real child-process termination around simulated emergency-close dispatch.

Only temporary databases and a fake gateway. No WEEX credentials or real writes.
Verifies the durable reservation prevents double submission after restart.
"""
import json,os,subprocess,sys,tempfile,sqlite3
from pathlib import Path
from weex_isolated_pilot_offline_journal import reserve,connect
from contextlib import closing
from weex_isolated_pilot_transport_harness import simulate_dispatch,schema

CHILD=r'''
import os,sys
from pathlib import Path
from weex_isolated_pilot_transport_harness import simulate_dispatch
class Fake:
 simulation_only=True
 def simulate(self,op,payload):
  path=Path(sys.argv[2]);path.write_text('FAKE_CLOSE_ACCEPTED')
  os._exit(77)
assert sys.argv[3]=='close'
simulate_dispatch(Path(sys.argv[1]),'pilot-crash','close',Fake())
raise AssertionError('EXPECTED_ABRUPT_EXIT')
'''

def run():
 import live_control
 root=Path(__file__).resolve().parent
 if live_control.state(root)['mode']!='STOPPED':raise PermissionError('MAIN_LIVE_NOT_STOPPED')
 with tempfile.TemporaryDirectory(prefix='weex_emergency_close_crash_') as tmp:
  folder=Path(tmp);db=folder/'pilot.sqlite3';exchange=folder/'fake_exchange_state.txt'
  reserve(db,pilot_id='pilot-crash',side='LONG',quantity='0.002',stop_price='2100')
  # Only the test fixture may advance fake state; never use in production.
  with closing(connect(db)) as c:
   with c:
    c.execute('UPDATE pilot_v1 SET state=? WHERE pilot_id=?',
              ('STOP_RECONCILED_EXTERNALLY','pilot-crash'))
  child=subprocess.run([sys.executable,'-c',CHILD,str(db),str(exchange),'close'],
       cwd=str(root),capture_output=True,text=True,timeout=20)
  if child.returncode!=77 or not exchange.is_file():
   raise AssertionError('FAKE_CLOSE_DID_NOT_CRASH_AFTER_ACCEPT')
  with closing(sqlite3.connect(str(db))) as c:
   state=c.execute("SELECT status FROM pilot_dispatch_v1 WHERE pilot_id=? AND stage='close'",
                   ('pilot-crash',)).fetchone()
  if not state or state[0]!='SIMULATION_OUTCOME_UNKNOWN':
   raise AssertionError('NO_DURABLE_CLOSE_RESERVATION')
  class UnexpectedRetry:
   simulation_only=True
   def simulate(self,*args):raise AssertionError('DUPLICATE_CLOSE')
  retry=simulate_dispatch(db,'pilot-crash','close',UnexpectedRetry())
  if retry['state']!='ALREADY_HANDLED_NO_RETRY':
   raise AssertionError('DUPLICATE_CLOSE_ALLOWED')
  return {'state':'OS_CRASH_AFTER_SIMULATED_CLOSE_ACCEPTANCE',
          'childExitCode':child.returncode,
          'durableCloseReservation':state[0],
          'restartDecision':retry['state'],
          'duplicateClosePrevented':True,
          'realWeexExitCertified':False,'realExchangeWrites':0,'mainBotMode':'STOPPED'}

if __name__=='__main__':print(json.dumps(run()))
