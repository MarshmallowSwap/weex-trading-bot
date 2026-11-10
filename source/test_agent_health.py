from datetime import datetime,timedelta,timezone
import sqlite3,unittest
from unittest.mock import patch
import agent_health

class Cursor:
 def __init__(self,row):self.row=row
 def fetchone(self):return self.row
class Connection:
 def __init__(self,row):self.row=row
 def execute(self,*args):return Cursor(self.row)
 def close(self):pass

class Check(unittest.TestCase):
 def setUp(self):
  now=datetime.now(timezone.utc).isoformat()
  self.row=(now,"OBSERVED","test")
  self.reports={
   "weex_execution_cycle_latest.json":{"checkedAt":now,"status":"OK","exchangeWrites":0},
   "weex_agent_orchestrator_latest.json":{"checkedAt":now,"cycleStatus":"OK","ordersSubmitted":False},
   "position_manager_integrated_latest.json":{"asOf":now,"completeWithinBounds":True}}
 def test_recent(self):
  with patch("agent_health.sqlite3.connect",return_value=Connection(self.row)),patch.object(agent_health,"load_report",side_effect=lambda name:self.reports[name]):
   self.assertEqual(agent_health.assess()["status"],"OK")
 def test_stale(self):
  old=((datetime.now(timezone.utc)-timedelta(hours=2)).isoformat(),"OBSERVED","test")
  with patch("agent_health.sqlite3.connect",return_value=Connection(old)):
   self.assertEqual(agent_health.assess()["status"],"STALE")
 def test_missing(self):
  with patch("agent_health.sqlite3.connect",side_effect=sqlite3.OperationalError("missing")):
   self.assertEqual(agent_health.assess()["status"],"ERROR")

if __name__=="__main__":unittest.main()
