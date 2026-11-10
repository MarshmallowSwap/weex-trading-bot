import tempfile,unittest
from pathlib import Path
from weex_live_manual_attestation import establish,classify
def p(sym,id,size):
 return {'id':id,'symbol':sym,'side':'SHORT','size':size,
         'openValue':str(float(size)*2),'cumOpenSize':size,
         'cumOpenValue':str(float(size)*2),'createdTime':100,
         'createdMatchSequenceId':123}
ROWS=[p('TRUTHUSDT',1,'10'),p('UAIUSDT',2,'20')]
class ManualAttestation(unittest.TestCase):
 def setUp(self):
  td=tempfile.TemporaryDirectory()
  self.addCleanup(td.cleanup);self.root=Path(td.name)
 def register(self):return establish(self.root,ROWS,user_attested=True)
 def test_register_two_exact(self):
  self.assertEqual(self.register()['state'],'ATTESTED_MANUAL_ONLY')
  self.assertTrue(classify(self.root,ROWS)['allPositionsUserAttested'])
 def test_repeat_identical_is_idempotent(self):
  self.register();self.assertEqual(self.register()['state'],'ALREADY_ATTESTED')
 def test_user_attestation_required(self):
  with self.assertRaises(PermissionError):establish(self.root,ROWS)
 def test_wrong_symbols_refused(self):
  with self.assertRaises(ValueError):
   establish(self.root,[ROWS[0],p('ETHUSDT',9,'1')],user_attested=True)
 def test_quantity_change_invalidates(self):
  self.register();other=[{**ROWS[0],'size':'11'},ROWS[1]]
  self.assertFalse(classify(self.root,other)['allPositionsUserAttested'])
 def test_position_id_change_invalidates(self):
  self.register();other=[{**ROWS[0],'id':99},ROWS[1]]
  self.assertFalse(classify(self.root,other)['allPositionsUserAttested'])
 def test_extra_position_invalidates(self):
  self.register();self.assertFalse(classify(self.root,ROWS+[p('BTCUSDT',4,'2')])['allPositionsUserAttested'])
 def test_missing_position_invalidates(self):
  self.register();self.assertFalse(classify(self.root,ROWS[:1])['allPositionsUserAttested'])
 def test_no_auto_trade_even_with_matching(self):
  self.register();result=classify(self.root,ROWS)
  self.assertFalse(result['allowsNewCrossEntries'])
  self.assertTrue(all(not x['canAutoClose'] and not x['canAutoProtect'] for x in result['positions']))
 def test_record_mutation_not_overwritten(self):
  self.register();other=[{**ROWS[0],'size':'15'},ROWS[1]]
  with self.assertRaises(ValueError):
   establish(self.root,other,user_attested=True)
if __name__=='__main__':unittest.main()
