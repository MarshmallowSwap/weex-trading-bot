"""A genuine OS-process crash drill using ONLY a temporary SQLite journal.

No exchange SDK, credentials, network, or real account state. Tests that a
process death after durable intent registration does not produce a duplicate
intent or make an UNKNOWN request eligible for exchange submission.
This is NOT evidence of a crash during a real WEEX order.
"""
import os,sys,json,subprocess,tempfile,sqlite3
from contextlib import closing
from pathlib import Path
from execution_intent_ledger import register
from weex_execution_cycle import exclusive

CHILD = r'''
import os,sys
from pathlib import Path
from execution_intent_ledger import register,mark_uncertain
from weex_execution_cycle import exclusive
db=Path(sys.argv[1]);lock=db.with_suffix('.lock');point=sys.argv[2]
with exclusive(lock):
 if point=='BEFORE_INTENT':
  os._exit(77)
 r=register('BTCUSDT','LONG','5','CRASH_DRILL_SIGNAL',db)
 if point=='AFTER_INTENT':
  os._exit(77)
 mark_uncertain(r['intentId'],db)
 if point=='AFTER_UNCERTAIN':
  os._exit(77)
 raise AssertionError('UNKNOWN_POINT')
'''

def run():
 import live_control
 root=Path(__file__).resolve().parent
 if live_control.state(root)['mode']!='STOPPED':
  raise PermissionError('LIVE_NOT_STOPPED')
 records=[]
 for point in ('BEFORE_INTENT','AFTER_INTENT','AFTER_UNCERTAIN'):
  with tempfile.TemporaryDirectory(prefix='weex_crash_drill_') as tmp:
   db=Path(tmp)/'intents.sqlite3';lock=db.with_suffix('.lock')
   child=subprocess.run([sys.executable,'-c',CHILD,str(db),point],
        cwd=str(root),timeout=15,check=False,capture_output=True,text=True)
   if child.returncode!=77:raise AssertionError('CHILD_DID_NOT_CRASH_AS_EXPECTED')
   # A process death must have released its OS-held lock, even though
   # its journal remains on disk. Still no order sending is possible.
   with exclusive(lock):
    resumed=register('BTCUSDT','LONG','5','CRASH_DRILL_SIGNAL',db)
    repeat=register('BTCUSDT','LONG','5','CRASH_DRILL_SIGNAL',db)
    with closing(sqlite3.connect(db)) as conn:
     count=conn.execute('SELECT COUNT(*) FROM intents').fetchone()[0]
   if (count!=1 or resumed['intentId']!=repeat['intentId']
        or resumed['canSubmitToExchange'] is not False
        or repeat['canSubmitToExchange'] is not False):
    raise AssertionError('IDEMPOTENCY_BROKEN')
   expected='UNKNOWN_RECONCILIATION_REQUIRED' if point=='AFTER_UNCERTAIN' else 'PENDING_REVIEW'
   if resumed['state']!=expected:raise AssertionError('STATE_CHANGED_AFTER_PROCESS_DEATH')
   records.append({'point':point,'childExitCode':child.returncode,
      'sqliteIntents':count,'sameDurableIntentAfterRestart':True,
      'osLockReacquired':True,'recoveredState':resumed['state'],
      'ordersSubmitted':0})
 if live_control.state(root)['mode']!='STOPPED':raise AssertionError('LIVE_CHANGED')
 return {'status':'REAL_OS_CRASH_LOCAL_JOURNAL_VERIFIED',
 'checks':records,'liveExchangeCrashCertified':False,'liveMode':'STOPPED',
 'exchangeOrdersSubmitted':0,'exchangeRequests':0}
if __name__=='__main__':print(json.dumps(run(),indent=2))
