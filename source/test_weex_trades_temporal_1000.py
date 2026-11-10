import unittest
from weex_trades_temporal_1000 import collect
def fill(i,time):return {'id':str(i),'orderId':'o'+str(i),'symbol':'ETHUSDT','time':time}
class Temporal(unittest.TestCase):
 def test_partial_page_exhaustion(self):
  r=collect(1000,fetch=lambda path:[fill(1,1000),fill(2,999)])
  self.assertEqual(r['tradeCount'],2)
  self.assertTrue(r['historyExhaustedWithinBounds'])
 def test_two_full_pages_then_partial(self):
  calls=[]
  def fetch(path):
   calls.append(path)
   if 'startTime=9901' in path:return [fill(99,9901)]
   if 'startTime=9801' in path:return [fill(199,9801)]
   if 'endTime=9900' in path:return [fill(i,10000-i) for i in range(100,200)]
   if 'endTime=9800' in path:return [fill(200,9800)]
   return [fill(i,10000-i) for i in range(100)]
  r=collect(1000,fetch=fetch)
  self.assertTrue(r['canCertifyCoverage'],r)
  self.assertEqual(r['tradeCount'],201)
  self.assertIn('endTime=9900',calls[2])
 def test_shared_oldest_boundary_fails_closed(self):
  def fetch(path):return [fill(i,10000-i if i<99 else 9902) for i in range(100)]
  r=collect(1000,fetch=fetch)
  self.assertFalse(r['canCertifyCoverage'])
  # last timestamp once, ambiguous "equal" cases tested separately
 def test_exactly_1000_cap(self):
  self.assertRaises(ValueError,collect,1001,lambda _:[])
 def test_conflicting_ids_fail(self):
  a=fill(1,1000)
  r=collect(1000,fetch=lambda _:[a,{**a,'time':999}])
  self.assertFalse(r['canCertifyCoverage'])
if __name__=='__main__':unittest.main()
