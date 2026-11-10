import sqlite3,unittest
from agent_watchdog import transition,init
class WatchTest(unittest.TestCase):
 def test_escalation_and_recovery(self):
  with sqlite3.connect(":memory:") as c:
   self.assertEqual(transition(c,"ERROR"),(None,1))
   self.assertEqual(transition(c,"ERROR"),("ERROR",2))
   c.execute("UPDATE watch SET last_notified='ERROR'")
   self.assertEqual(transition(c,"ERROR")[0],None)
   self.assertEqual(transition(c,"OK")[0],"RECOVERED")
   c.execute("UPDATE watch SET last_notified='OK'")
   self.assertEqual(transition(c,"OK")[0],None)
 def test_stale(self):
  with sqlite3.connect(":memory:") as c:
   transition(c,"STALE")
   self.assertEqual(transition(c,"STALE"),("STALE",2))
if __name__=="__main__":unittest.main()
