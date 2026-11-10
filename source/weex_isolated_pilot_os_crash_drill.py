"""Real OS process crash against isolated pilot SQLite and fake gateway only.

No exchange credentials, network access, actual orders, or live approval.
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from contextlib import closing

from weex_isolated_pilot_offline_journal import reserve,connect
from weex_isolated_pilot_transport_harness import simulate_dispatch,schema

CHILD = r'''
import os,sys
from weex_isolated_pilot_transport_harness import simulate_dispatch
class AbruptFake:
    simulation_only=True
    def simulate(self,operation,payload):
        os._exit(73)
simulate_dispatch(sys.argv[1],'crash-test','entry',AbruptFake())
raise AssertionError('EXPECTED_PROCESS_CRASH')
'''

class NoRetryFake:
    simulation_only=True
    def __init__(self):self.calls=0
    def simulate(self,operation,payload):
        self.calls+=1
        raise AssertionError('DUPLICATE_DISPATCH')

def run():
    import live_control
    root=Path(__file__).resolve().parent
    if live_control.state(root)['mode']!='STOPPED':
        raise PermissionError('LIVE_NOT_STOPPED')
    with tempfile.TemporaryDirectory(prefix='weex_isolated_1x_crash_') as folder:
        db=Path(folder)/'pilot.sqlite3'
        reserve(db,pilot_id='crash-test',side='LONG',quantity='0.002',stop_price='2100')
        child=subprocess.run([sys.executable,'-c',CHILD,str(db)],cwd=root,
                             capture_output=True,text=True,timeout=15)
        with closing(connect(db)) as conn:
            schema(conn)
            persisted=conn.execute(
                "SELECT status FROM pilot_dispatch_v1 WHERE pilot_id='crash-test' AND stage='entry'"
            ).fetchone()
        fake=NoRetryFake()
        after=simulate_dispatch(db,'crash-test','entry',fake)
        # Entry is not independently confirmed. Stop and close must remain blocked.
        stop=simulate_dispatch(db,'crash-test','stop',fake)
        close=simulate_dispatch(db,'crash-test','close',fake)
        passed=(child.returncode==73 and persisted is not None and
                persisted[0]=='SIMULATION_OUTCOME_UNKNOWN' and
                after['state']=='ALREADY_HANDLED_NO_RETRY' and fake.calls==0 and
                stop['state']=='PREREQUISITE_NOT_CERTIFIED' and
                close['state']=='PREREQUISITE_NOT_CERTIFIED')
        return {'passed':passed,'childExitCode':child.returncode,
                'durableState':persisted[0] if persisted else None,
                'restartDecision':after['state'],
                'stopDecision':stop['state'],'closeDecision':close['state'],
                'duplicateSimulationCalls':fake.calls,
                'realWEEXCrashTested':False,'exchangeWrites':0,
                'liveAuthorization':False}
if __name__=='__main__':
    out=run()
    print(json.dumps(out))
    raise SystemExit(0 if out['passed'] else 1)
