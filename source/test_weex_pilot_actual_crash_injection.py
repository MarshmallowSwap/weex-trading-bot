"""Offline subprocess crash-injection: no exchange writes, no credentials.
A child exits abruptly after the one-shot durable reservation (the precise
crash window before the HTTP result). A newly spawned Python process must
find UNKNOWN and refuse a second dispatch. Synthetic exchange fixture based
on recorded demo snapshot verifies recovery of the same exact client ID.
"""
import json,subprocess,sys,tempfile,unittest
from pathlib import Path
from contextlib import closing
from weex_isolated_pilot_offline_journal import reserve,connect
from weex_pilot_attach_atomic_stop import attach
from weex_pilot_dispatch_readback_run import pending
from weex_pilot_dispatch_reconciliation import reconcile

ROOT=Path(__file__).resolve().parent
CRASH_SCRIPT="""
import os,sys,json
from pathlib import Path
from weex_pilot_guarded_entry_dispatch import send_entry_once
from weex_pilot_protected_entry_sdk import ProtectedEntryTransport
class CrashAfterReservation(ProtectedEntryTransport):
    def preflight_entry(self,*a,**k):return True
    def send_entry_only(self,*a,**k):
        os._exit(73)
db=Path(sys.argv[1])
send_entry_once(db,'CRASH',ask='2227.99',
    account={'fresh':True},transport=CrashAfterReservation(db.parent))
raise RuntimeError('SHOULD_NEVER_RETURN')
"""
RETRY_SCRIPT="""
import json,sys
from pathlib import Path
from weex_pilot_guarded_entry_dispatch import send_entry_once
from weex_pilot_protected_entry_sdk import ProtectedEntryTransport
from weex_pilot_dispatch_readback_run import pending
class ForbiddenSend(ProtectedEntryTransport):
    calls=0
    def preflight_entry(self,*a,**k):
        raise RuntimeError('PREFLIGHT_MUST_NOT_RUN_ON_RESERVED_INTENT')
    def send_entry_only(self,*a,**k):
        self.calls+=1;raise RuntimeError('DUPLICATE_DISPATCH')
db=Path(sys.argv[1]);transport=ForbiddenSend(db.parent)
result=send_entry_once(db,'CRASH',ask='2227.99',account={},
                       transport=transport)
print(json.dumps({'pending':pending(db),'dispatch':result,'calls':transport.calls}))
"""
class CrashRecovery(unittest.TestCase):
    def test_os_exit_after_dispatch_reservation_never_resends(self):
        with tempfile.TemporaryDirectory() as tmp:
            db=Path(tmp)/'pilot.sqlite3'
            reserve(db,pilot_id='CRASH',side='LONG',quantity='0.002',stop_price='2194.57')
            attach(db,'CRASH',stop='2194.57',reference_price='2227.99')
            child=subprocess.run([sys.executable,'-c',CRASH_SCRIPT,str(db)],
                capture_output=True,text=True,timeout=18,cwd=ROOT)
            self.assertEqual(child.returncode,73,child.stderr)
            with closing(connect(db)) as c:
                state=c.execute("SELECT state FROM pilot_entry_dispatch_v1 WHERE pilot_id='CRASH'").fetchone()
                self.assertEqual(state,('OUTCOME_UNKNOWN',))
            child2=subprocess.run([sys.executable,'-c',RETRY_SCRIPT,str(db)],
                capture_output=True,text=True,timeout=18,cwd=ROOT,check=True)
            result=json.loads(child2.stdout)
            self.assertEqual(result['calls'],0)
            self.assertEqual(result['pending'],[['CRASH','entry']])
            self.assertEqual(result['dispatch']['state'],'ALREADY_RESERVED_NO_RETRY')
            # Exact exchange readback may later reconcile UNKNOWN. Build a
            # clearly synthetic copy using actual observed WEEX demo shapes.
            trial=json.loads((ROOT/'weex_sim_eth_trial_readback_latest.json').read_text())
            with closing(connect(db)) as c:
                cid=c.execute("SELECT entry_id FROM pilot_v1 WHERE pilot_id='CRASH'").fetchone()[0]
            order={**trial['get_capi_v3_order'],'clientOrderId':cid}
            stop={**trial['get_capi_v3_openAlgoOrders'][0],'clientAlgoId':cid+'sl'}
            fills=trial['get_capi_v3_userTrades']
            pos=trial['get_capi_v3_account_position_allPosition']
            proof=reconcile(db,'CRASH','entry',order=order,fills=fills,
                positions=pos,regular_orders=[],conditional_orders=[stop])
            self.assertTrue(proof['confirmed'],proof)
            self.assertEqual(pending(db),[])
            with closing(connect(db)) as c:
                final=c.execute("SELECT state FROM pilot_v1 WHERE pilot_id='CRASH'").fetchone()[0]
            self.assertEqual(final,'ENTRY_RECONCILED_EXTERNALLY')
    def test_crash_absence_of_exchange_proof_stays_unknown(self):
        with tempfile.TemporaryDirectory() as tmp:
            db=Path(tmp)/'pilot.sqlite3'
            reserve(db,pilot_id='CRASH',side='LONG',quantity='0.002',stop_price='2194.57')
            attach(db,'CRASH',stop='2194.57',reference_price='2227.99')
            child=subprocess.run([sys.executable,'-c',CRASH_SCRIPT,str(db)],
                capture_output=True,text=True,timeout=18,cwd=ROOT)
            self.assertEqual(child.returncode,73)
            r=reconcile(db,'CRASH','entry',order=None,fills=[],
                 positions=[],regular_orders=[],conditional_orders=[])
            self.assertFalse(r['confirmed'])
            self.assertEqual(pending(db),[('CRASH','entry')])
if __name__=='__main__':unittest.main()
