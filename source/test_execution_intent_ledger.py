import unittest,tempfile
from pathlib import Path
from execution_intent_ledger import register,mark_uncertain,connect
class LedgerTests(unittest.TestCase):
 def test_duplicate(self):
  with tempfile.TemporaryDirectory() as t:
   db=Path(t)/"intents.db"
   a=register("BTCUSDT","LONG",5,"signal-123",db)
   b=register("BTCUSDT","LONG",5,"signal-123",db)
   self.assertEqual(a["intentId"],b["intentId"])
   self.assertFalse(a["canSubmitToExchange"])
   self.assertEqual(mark_uncertain(a["intentId"],db),1)
   c=register("BTCUSDT","LONG",5,"signal-123",db)
   self.assertEqual(c["state"],"UNKNOWN_RECONCILIATION_REQUIRED")
 def test_bad_margin(self):
  with self.assertRaises(ValueError):register("BTCUSDT","LONG",-5,"sig")
 def test_unique_signal(self):
  with tempfile.TemporaryDirectory() as t:
   db=Path(t)/"intents.db"
   a=register("BTCUSDT","LONG",5,"a",db)
   b=register("BTCUSDT","LONG",5,"b",db)
   self.assertNotEqual(a["intentId"],b["intentId"])
if __name__=="__main__":unittest.main()
