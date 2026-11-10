"""Full three-stage pilot lifecycle tests against a fake exchange and temporary DB.

All stage progress is SIMULATED and never transferred into the live journal.
"""
import tempfile
import unittest
from pathlib import Path
from contextlib import closing
from weex_isolated_pilot_offline_journal import reserve,connect
from weex_isolated_pilot_transport_harness import simulate_dispatch,schema

class FakeExchange:
    simulation_only=True
    def __init__(self):
        self.calls=[]
    def simulate(self,op,payload):
        self.calls.append((op,payload))
        return {'success':True,'orderId':'SIM-'+str(len(self.calls))}

def fake_observed_stage(db,pilot_id,from_state,to_state):
    """Simulation-only stage transition, never run against the production DB."""
    with closing(connect(db)) as c:
        c.execute('BEGIN IMMEDIATE')
        row=c.execute('SELECT state FROM pilot_v1 WHERE pilot_id=?',(pilot_id,)).fetchone()
        if row is None or row[0]!=from_state:
            c.rollback()
            return False
        c.execute('UPDATE pilot_v1 SET state=? WHERE pilot_id=?',(to_state,pilot_id))
        c.commit()
        return True

class FullSimulatedPilotLifecycle(unittest.TestCase):
    def test_entry_stop_close_restarts_no_duplicate(self):
        with tempfile.TemporaryDirectory(prefix='pilot_sim_only_') as folder:
            db=Path(folder)/'journal.sqlite3'
            reserve(db,pilot_id='offline-case',side='LONG',quantity='0.002',stop_price='2100')
            fake=FakeExchange()
            entry=simulate_dispatch(db,'offline-case','entry',fake)
            self.assertEqual(entry['state'],'SIMULATED_ACK_ONLY')
            self.assertFalse(entry['nextStageAuthorized'])
            self.assertEqual(simulate_dispatch(db,'offline-case','stop',fake)['state'],'PREREQUISITE_NOT_CERTIFIED')
            # The fake exchange has confirmed the entry only in the temp test.
            self.assertTrue(fake_observed_stage(db,'offline-case','PREPARED_NO_SEND','ENTRY_RECONCILED_EXTERNALLY'))
            stop=simulate_dispatch(db,'offline-case','stop',fake)
            self.assertEqual(stop['state'],'SIMULATED_ACK_ONLY')
            self.assertEqual(simulate_dispatch(db,'offline-case','close',fake)['state'],'PREREQUISITE_NOT_CERTIFIED')
            self.assertTrue(fake_observed_stage(db,'offline-case','ENTRY_RECONCILED_EXTERNALLY','STOP_RECONCILED_EXTERNALLY'))
            close=simulate_dispatch(db,'offline-case','close',fake)
            self.assertEqual(close['state'],'SIMULATED_ACK_ONLY')
            self.assertEqual(len(fake.calls),3)
            # Re-open the durable DB as a new caller after all three stages.
            restarted=FakeExchange()
            for stage in ('entry','stop','close'):
                result=simulate_dispatch(db,'offline-case',stage,restarted)
                self.assertEqual(result['state'],'ALREADY_HANDLED_NO_RETRY')
                self.assertFalse(result['sentRealOrders'])
            self.assertEqual(restarted.calls,[])
            with closing(connect(db)) as c:
                schema(c)
                statuses=dict(c.execute('SELECT stage,status FROM pilot_dispatch_v1'))
            self.assertEqual(statuses,{'entry':'SIMULATED_ACK_ONLY',
                                      'stop':'SIMULATED_ACK_ONLY',
                                      'close':'SIMULATED_ACK_ONLY'})
            self.assertEqual(fake.calls[0][1]['symbol'],'ETHUSDT')
            self.assertTrue(fake.calls[1][1]['reduceOnly'])
            self.assertTrue(fake.calls[2][1]['reduceOnly'])
    def test_uncertain_entry_never_advances_without_simulated_evidence(self):
        with tempfile.TemporaryDirectory(prefix='pilot_sim_only_') as folder:
            db=Path(folder)/'journal.sqlite3'
            reserve(db,pilot_id='unknown-case',side='SHORT',quantity='0.002',stop_price='2500')
            class TimeoutFake:
                simulation_only=True
                calls=0
                def simulate(self,op,payload):
                    self.calls+=1
                    raise TimeoutError('SIM_ONLY')
            fake=TimeoutFake()
            self.assertEqual(simulate_dispatch(db,'unknown-case','entry',fake)['state'],
                             'SIMULATION_OUTCOME_UNKNOWN')
            self.assertEqual(simulate_dispatch(db,'unknown-case','entry',fake)['state'],
                             'ALREADY_HANDLED_NO_RETRY')
            self.assertEqual(simulate_dispatch(db,'unknown-case','stop',fake)['state'],
                             'PREREQUISITE_NOT_CERTIFIED')
            self.assertEqual(fake.calls,1)
if __name__=='__main__':unittest.main()
