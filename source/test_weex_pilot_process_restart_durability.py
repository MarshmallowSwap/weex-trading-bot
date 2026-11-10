"""Process restart proof for durable pilot one-shot reservation.

Runs a separate Python process to reload the pending journal and ensures the
same dispatch cannot be resent, even after process loss. Offline proof only.
"""
import json,subprocess,sys,tempfile,unittest
from pathlib import Path
from contextlib import closing
from weex_isolated_pilot_offline_journal import reserve,connect
from weex_pilot_dispatch_readback_run import pending
class RestartDurability(unittest.TestCase):
 def test_unknown_entry_survives_restart_and_no_resend(self):
  with tempfile.TemporaryDirectory() as td:
   db=Path(td)/'pilot.sqlite3'
   reserve(db,pilot_id='P',side='LONG',quantity='0.002',stop_price='2100')
   with closing(connect(db)) as c:
    cid=c.execute('SELECT entry_id FROM pilot_v1 WHERE pilot_id=?',('P',)).fetchone()[0]
    c.execute('''CREATE TABLE pilot_entry_dispatch_v1(
      pilot_id TEXT PRIMARY KEY, client_id TEXT UNIQUE,
      state TEXT NOT NULL,response TEXT)''')
    c.execute('INSERT INTO pilot_entry_dispatch_v1 VALUES(?,?,?,NULL)',
              ('P',cid,'OUTCOME_UNKNOWN'))
    c.commit()
   self.assertEqual(pending(db),[('P','entry')])
   command=('import json,sys;from pathlib import Path;'
            'from weex_pilot_dispatch_readback_run import pending;'
            'print(json.dumps(pending(Path(sys.argv[1]))))')
   p=subprocess.run([sys.executable,'-c',command,str(db)],
                    capture_output=True,text=True,timeout=15,check=True)
   self.assertEqual(json.loads(p.stdout),[['P','entry']])
   with closing(connect(db)) as c:
    self.assertEqual(c.execute('SELECT state FROM pilot_entry_dispatch_v1').fetchone()[0],
                     'OUTCOME_UNKNOWN')
 def test_unknown_emergency_survives_restart(self):
  with tempfile.TemporaryDirectory() as td:
   db=Path(td)/'pilot.sqlite3'
   reserve(db,pilot_id='P',side='LONG',quantity='0.002',stop_price='2100')
   with closing(connect(db)) as c:
    c.execute('''CREATE TABLE pilot_emergency_dispatch_v1(
      pilot_id TEXT PRIMARY KEY,position_id TEXT,state TEXT,response TEXT)''')
    c.execute('INSERT INTO pilot_emergency_dispatch_v1 VALUES (?,?,?,NULL)',
              ('P','123','OUTCOME_UNKNOWN'))
    c.commit()
   command=('import json,sys;from pathlib import Path;'
            'from weex_pilot_dispatch_readback_run import pending;'
            'print(json.dumps(pending(Path(sys.argv[1]))))')
   p=subprocess.run([sys.executable,'-c',command,str(db)],
                    capture_output=True,text=True,timeout=15,check=True)
   self.assertEqual(json.loads(p.stdout),[['P','emergency']])
if __name__=='__main__':unittest.main()
