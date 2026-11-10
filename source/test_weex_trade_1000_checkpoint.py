import unittest,tempfile
from pathlib import Path
from weex_trades_temporal_1000 import collect
def trade(i,t):return {'id':str(i),'orderId':'order-'+str(i),'symbol':'ETHUSDT','time':t}
class CursorCheckpoint(unittest.TestCase):
 def test_resume_without_repeating_first_page(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/'cursor.json';calls=[]
   def fetch(url):
    calls.append(url)
    if 'startTime=' in url:
     return [trade(99,9901)]
    if 'endTime=9900' in url:
     return [trade(100,9900),trade(101,9899)]
    return [trade(i,10000-i) for i in range(100)]
   first=collect(1000,fetch=fetch,max_batches=2,checkpoint_path=p)
   self.assertEqual(first['tradeCount'],100)
   self.assertTrue(p.exists())
   calls.clear()
   second=collect(1000,fetch=fetch,max_batches=2,checkpoint_path=p)
   self.assertTrue(second['canCertifyCoverage'],second)
   self.assertEqual(second['tradeCount'],102)
   self.assertEqual(len(calls),1)
   self.assertIn('endTime=9900',calls[0])
 def test_missing_boundary_fails_without_checkpoint(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/'cursor.json'
   def fetch(url):
    if 'startTime=' in url:return []
    return [trade(i,10000-i) for i in range(100)]
   r=collect(1000,fetch=fetch,max_batches=3,checkpoint_path=p)
   self.assertFalse(r['canCertifyCoverage'])
   self.assertEqual(r['paginationFailure'],'BOUNDARY_IDS_NOT_RECOVERED')
   self.assertFalse(p.exists())
 def test_duplicate_id_conflict_denied(self):
  def fetch(url):
   if 'startTime=' in url:return [trade(99,9901)]
   return [trade(i,10000-i) for i in range(100)]
  r=collect(1000,fetch=fetch,max_batches=2)
  self.assertEqual(r['tradeCount'],100)
if __name__=='__main__':unittest.main()
