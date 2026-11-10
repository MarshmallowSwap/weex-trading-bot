import tempfile,unittest,json
from pathlib import Path
from unittest.mock import patch
from weex_pilot_flat_baseline_readonly import capture
class Reader:
 def __init__(self,positions=None,orders=None,algos=None):
  self.rows=(positions or [],orders or [],algos or [])
 def account(self):return self.rows
class Baseline(unittest.TestCase):
 def setup_env(self,t):
  root=Path(t)
  import sqlite3
  from contextlib import closing
  with closing(sqlite3.connect(root/'weex_isolated_pilot.sqlite3')) as db:
   db.execute('CREATE TABLE pilot_v1(pilot_id TEXT)')
   db.commit()
  return root
 def test_verified_flat_snapshot_no_send(self):
  with tempfile.TemporaryDirectory() as t:
   root=self.setup_env(t)
   with patch('live_control.state',return_value={'mode':'STOPPED'}),patch('live_control.build_errors',return_value=[]):
    x=capture(root,Reader())
   self.assertFalse(x['canSend']);self.assertEqual(x['exchangeWrites'],0)
   self.assertTrue((root/'weex_pilot_flat_baseline_latest.json').exists())
 def test_existing_position_denied(self):
  with tempfile.TemporaryDirectory() as t:
   root=self.setup_env(t)
   with patch('live_control.state',return_value={'mode':'STOPPED'}),patch('live_control.build_errors',return_value=[]):
    with self.assertRaisesRegex(PermissionError,'ACCOUNT_NOT_FLAT'):
     capture(root,Reader(positions=[{'symbol':'ETHUSDT'}]))
 def test_main_running_denied(self):
  with tempfile.TemporaryDirectory() as t:
   root=self.setup_env(t)
   with patch('live_control.state',return_value={'mode':'RUNNING'}):
    with self.assertRaises(PermissionError):capture(root,Reader())
 def test_integrity_failure_denied(self):
  with tempfile.TemporaryDirectory() as t:
   root=self.setup_env(t)
   with patch('live_control.state',return_value={'mode':'STOPPED'}),patch('live_control.build_errors',return_value=['MODIFIED']):
    with self.assertRaises(PermissionError):capture(root,Reader())
if __name__=='__main__':unittest.main()
