import json,tempfile,unittest
from pathlib import Path
from weex_manual_position_ack import key,identity,ACKS
from weex_live_existing_telegram_ack_shadow import assess
P=[{'id':11,'symbol':'TRUTHUSDT','side':'SHORT','size':'3','openValue':'50',
 'cumOpenSize':'3','cumOpenValue':'50','createdTime':1,'createdMatchSequenceId':5},
 {'id':12,'symbol':'UAIUSDT','side':'SHORT','size':'4','openValue':'70',
 'cumOpenSize':'4','cumOpenValue':'70','createdTime':2,'createdMatchSequenceId':6}]
class ExistingAck(unittest.TestCase):
 def setUp(self):
  td=tempfile.TemporaryDirectory();self.addCleanup(td.cleanup)
  self.root=Path(td.name)
  (self.root/ACKS).write_text(json.dumps({key(P[1]):{'identity':identity(P[1]),
          'acknowledgedAt':100,'user':'test','chat':'test'}}))
 def test_only_second_ack(self):
  r=assess(self.root,P)
  self.assertEqual(r['confirmedPositions'],1)
  self.assertEqual([x['telegramAckConfirmed'] for x in r['positions']],[False,True])
 def test_no_new_entries(self):
  r=assess(self.root,P)
  self.assertFalse(r['newEntriesAuthorized'])
  self.assertFalse(r['manualOrderModificationAuthorized'])
 def test_position_changed_revokes(self):
  r=assess(self.root,[P[0],{**P[1],'size':'5'}])
  self.assertEqual(r['confirmedPositions'],0)
 def test_missing_ack_file_fails_closed(self):
  (self.root/ACKS).unlink()
  self.assertEqual(assess(self.root,P)['confirmedPositions'],0)
 def test_invalid_position_fails(self):
  self.assertEqual(assess(self.root,[None])['status'],'INVALID_POSITIONS')
if __name__=='__main__':unittest.main()
