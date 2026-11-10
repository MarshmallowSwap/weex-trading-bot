import tempfile,unittest
from pathlib import Path
from weex_partial_guardian_persistent import register,evaluate,finalize_closed,dbopen
from test_weex_partial_guardian_replay import B,POS,NSL,NTP
class FinalizeTests(unittest.TestCase):
 def setUp(self):
  td=tempfile.TemporaryDirectory();self.addCleanup(td.cleanup)
  self.path=str(Path(td.name)/'guardian.sqlite')
  register(self.path,'t',**B)
  self.assertEqual(evaluate(self.path,'t',positions=POS,algos=[NSL,NTP],
      regular_orders=[],authenticated_sim_readback=True)['state'],
      'PAIR_RESTORED_OFFLINE_ONLY')
 def finish(self,positions=None,algos=None,regular=None,verified=True):
  return finalize_closed(self.path,'t',positions=[] if positions is None else positions,
       algos=[] if algos is None else algos,regular_orders=[] if regular is None else regular,
       authenticated_sim_readback=verified)
 def test_closed_after_complete_readback(self):
  self.assertEqual(self.finish()['state'],'CLOSED_CONFIRMED')
  self.assertTrue(self.finish()['alreadyFinal'])
  conn=dbopen(self.path)
  try:
   self.assertEqual(conn.execute('SELECT count(*) FROM events WHERE event=?',
                       ('CLOSED_CONFIRMED',)).fetchone()[0],1)
  finally:
   conn.close()
 def test_open_position_refused(self):
  self.assertEqual(self.finish(positions=POS)['reason'],'POSITION_STILL_OBSERVED')
 def test_remaining_stop_refused(self):
  self.assertEqual(self.finish(algos=[NSL])['reason'],'ORDER_STILL_OBSERVED')
 def test_unverified_readback_refused(self):
  self.assertEqual(self.finish(verified=False)['reason'],'COMPLETE_AUTHENTICATED_READBACK_REQUIRED')
 def test_normal_order_refused(self):
  self.assertEqual(self.finish(regular=[{'symbol':'BTCUSDT'}])['reason'],'ORDER_STILL_OBSERVED')
 def test_missing_readback_refused(self):
  self.assertEqual(finalize_closed(self.path,'t',positions=[],algos=None,regular_orders=[],
                authenticated_sim_readback=True)['reason'],'COMPLETE_AUTHENTICATED_READBACK_REQUIRED')
if __name__=='__main__':unittest.main()
