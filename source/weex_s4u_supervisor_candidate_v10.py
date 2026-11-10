"""Noninteractive S4U supervisor preflight; never dispatches exchange writes.

Reads authenticated account GET and local durable journal, performs one
isolated supervisor tick with a mock 'no pending crash' observer, and
writes separate result file. Does NOT touch production monitor heartbeat.
"""
from pathlib import Path
import json,os,sqlite3,time,traceback
ROOT=Path(__file__).resolve().parent
OUTPUT=ROOT/'weex_s4u_supervisor_candidate_v10.json'
def main():
 result={'checkedAtEpoch':time.time(),'pid':os.getpid(),
     'accountFlat':False,'lifecycleReadable':False,
     'isolatedMonitorTickPass':False,'networkWrites':0,
     'productionMonitorTouched':False,'status':'S4U_CANDIDATE_BLOCKED'}
 try:
  import live_control
  if live_control.state(ROOT).get('mode')!='STOPPED' or live_control.build_errors(ROOT):
   raise RuntimeError('PRODUCTION_NOT_STOPPED_OR_INTEGRITY_ERROR')
  from weex_live_worker import Reader
  positions,orders,algos=Reader(ROOT).account()
  if not all(isinstance(v,list) for v in (positions,orders,algos)):
   raise RuntimeError('ACCOUNT_RESPONSE_INVALID')
  result['accountFlat']=not (positions or orders or algos)
  if not result['accountFlat']:raise RuntimeError('ACCOUNT_NOT_FLAT')
  db=ROOT/'weex_user_live_lifecycle.sqlite3'
  with sqlite3.connect('file:'+db.resolve().as_posix()+'?mode=ro',uri=True) as c:
   c.execute('PRAGMA query_only=ON')
   c.execute("SELECT count(*) FROM sqlite_master").fetchone()
  result['lifecycleReadable']=True
  from weex_supervised_process_monitor_v6 import tick
  import tempfile
  with tempfile.TemporaryDirectory(prefix='weex_s4u_isolated_monitor_') as temp:
   report=tick(temp,observer=lambda root:{'status':'NO_PENDING_CRASH_INTENT'})
   result['isolatedMonitorTickPass']=(report.get('status')=='OBSERVING_NOT_ARMED'
       and report.get('entryDispatchAllowed') is False
       and report.get('closeDispatchAllowed') is False
       and report.get('possibleReduceOnlyClosePosts')==0)
  if not result['isolatedMonitorTickPass']:raise RuntimeError('ISOLATED_TICK_FAILED')
  result['status']='S4U_CANDIDATE_PASS'
 except Exception as exc:
  result['failureType']=type(exc).__name__
  result['failureCode']=str(exc)[:120] if type(exc).__name__=='RuntimeError' else type(exc).__name__
 finally:
  temp=OUTPUT.with_name(OUTPUT.name+'.'+str(os.getpid())+'.tmp')
  temp.write_text(json.dumps(result,sort_keys=True)+'\n',encoding='utf-8')
  os.replace(temp,OUTPUT)
  print(json.dumps(result,ensure_ascii=False),flush=True)
 if result['status']!='S4U_CANDIDATE_PASS':raise SystemExit(2)
if __name__=='__main__':main()
