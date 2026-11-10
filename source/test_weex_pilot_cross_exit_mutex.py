"""Verify both pilot exits mutually exclude one another on the same journal."""
import unittest,tempfile,json
from pathlib import Path
from contextlib import closing
from weex_isolated_pilot_offline_journal import reserve,connect
from weex_pilot_guarded_close_dispatch import dispatch_close
from weex_pilot_emergency_dispatch import dispatch as emergency

class FallbackTransport:
    pilot_emergency_close_only=True
    count=0
    def send_emergency_close(self,op,p):
        self.count+=1
        return {'success':True,'orderId':'FAKE_ACK'}

class ReduceTransport:
    pilot_live_close_only=True
    count=0
    def send_close_only(self,op,p):
        self.count+=1
        return {'success':True,'orderId':'FAKE_ACK'}

def setup(root):
    db=root/'pilot.db'
    reserve(db,pilot_id='P',side='LONG',quantity='0.002',stop_price='2000')
    with closing(connect(db)) as c:
        entry,raw=c.execute('SELECT entry_id,proposals FROM pilot_v1').fetchone()
        c.execute("UPDATE pilot_v1 SET state='ENTRY_RECONCILED_EXTERNALLY'")
        c.commit()
    owner={'owned':True,'positionId':'123456789','clientOrderId':entry,'quantity':'0.002'}
    pos={'symbol':'ETHUSDT','id':'123456789','marginType':'ISOLATED','side':'LONG','size':'0.002'}
    proposal={'prepared':True,'canSend':False,'payload':json.loads(raw)['close']}
    return db,owner,pos,proposal

class CrossExitMutex(unittest.TestCase):
    def test_reduce_only_claim_blocks_position_close(self):
        with tempfile.TemporaryDirectory() as t:
            db,owner,pos,proposal=setup(Path(t))
            reduce=ReduceTransport();fallback=FallbackTransport()
            r=dispatch_close(db,'P',proposal,ownership=owner,account_fresh=True,transport=reduce)
            self.assertEqual(r['state'],'ACK_RECEIVED_UNRECONCILED')
            with self.assertRaisesRegex(PermissionError,'ANOTHER_EXIT_ALREADY_RESERVED'):
                emergency(db,'P',ownership=owner,observed_position=pos,transport=fallback)
            self.assertEqual(reduce.count,1)
            self.assertEqual(fallback.count,0)
    def test_position_close_claim_blocks_reduce_only(self):
        with tempfile.TemporaryDirectory() as t:
            db,owner,pos,proposal=setup(Path(t))
            reduce=ReduceTransport();fallback=FallbackTransport()
            r=emergency(db,'P',ownership=owner,observed_position=pos,transport=fallback)
            self.assertEqual(r['state'],'ACK_RECEIVED_NEEDS_EXCHANGE_READBACK')
            with self.assertRaisesRegex(PermissionError,'ANOTHER_EXIT_ALREADY_RESERVED'):
                dispatch_close(db,'P',proposal,ownership=owner,account_fresh=True,transport=reduce)
            self.assertEqual(fallback.count,1)
            self.assertEqual(reduce.count,0)
    def test_unknown_result_keeps_mutex(self):
        class Faulty(ReduceTransport):
            def send_close_only(self,op,p):
                self.count+=1
                raise TimeoutError('uncertain')
        with tempfile.TemporaryDirectory() as t:
            db,owner,pos,proposal=setup(Path(t))
            r=dispatch_close(db,'P',proposal,ownership=owner,account_fresh=True,transport=Faulty())
            self.assertEqual(r['state'],'OUTCOME_UNKNOWN')
            with self.assertRaisesRegex(PermissionError,'ANOTHER_EXIT_ALREADY_RESERVED'):
                emergency(db,'P',ownership=owner,observed_position=pos,transport=FallbackTransport())
if __name__=='__main__':unittest.main()
