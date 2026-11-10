import unittest,tempfile
from pathlib import Path
from execution_lifecycle import create,transition,timeline
class Lifecycle(unittest.TestCase):
 def test_happy_path(self):
  with tempfile.TemporaryDirectory() as d:
   path=Path(d)/"db.sqlite";ident=create(path,"test1")
   for state in ("APPROVED","SUBMISSION_UNKNOWN","ACKNOWLEDGED","OPEN","PARTIAL","FILLED"):
    self.assertTrue(transition(ident,state,path))
   self.assertEqual(len(timeline(ident,path)),7)
   with self.assertRaises(ValueError):transition(ident,"OPEN",path)
 def test_idempotent_event(self):
  with tempfile.TemporaryDirectory() as d:
   path=Path(d)/"db.sqlite";ident=create(path,"same")
   create(path,"same")
   self.assertEqual(len(timeline(ident,path)),1)
   transition(ident,"RISK_REJECTED",path)
   self.assertFalse(transition(ident,"RISK_REJECTED",path))
 def test_uncertain_reconcile(self):
  with tempfile.TemporaryDirectory() as d:
   path=Path(d)/"db.sqlite";ident=create(path)
   transition(ident,"APPROVED",path);transition(ident,"SUBMISSION_UNKNOWN",path)
   transition(ident,"RECONCILIATION_REQUIRED",path)
   transition(ident,"PARTIAL",path)
   self.assertEqual(timeline(ident,path)[-1][1],"PARTIAL")
 def test_invalid(self):
  with tempfile.TemporaryDirectory() as d:
   path=Path(d)/"db.sqlite";ident=create(path)
   with self.assertRaises(ValueError):transition(ident,"FILLED",path)
if __name__=="__main__":unittest.main()
