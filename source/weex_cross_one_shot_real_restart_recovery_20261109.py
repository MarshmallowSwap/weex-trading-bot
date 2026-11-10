"""Real WEEX GET-only restart recovery of the finished CROSS 1x pilot.

Abrupt child termination happens during authenticated read, NOT during a
real exchange write. Restarted independent process recovers exact entry,
close and terminal stop; original one-shot journal prevents duplicate send.
"""
import hashlib,json,os,subprocess,sys
from pathlib import Path
from datetime import datetime,timezone

ROOT=Path(__file__).resolve().parent
PYTHON=sys.executable
JOURNAL=ROOT/'weex_cross_one_shot_real_pilot_20261109.json'
AUDIT=ROOT/'weex_cross_one_shot_real_independent_audit_20261109.json'
REPORT=ROOT/'weex_cross_one_shot_real_restart_recovery_20261109.json'
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def run_child(code,timeout=22):
 return subprocess.run([PYTHON,'-c',code],cwd=ROOT,encoding='utf-8',
                       stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                       timeout=timeout)
def go():
 if not JOURNAL.is_file():raise FileNotFoundError('REAL_ORDER_JOURNAL_MISSING')
 if REPORT.exists():
  print('ALREADY_VERIFIED_NOT_REPEATING');return
 original=json.loads(JOURNAL.read_text(encoding='utf-8'))
 if (original.get('stage')!='CROSS_PILOT_CLOSED_AND_VERIFIED'
     or original.get('entryPostCount')!=1 or original.get('closePostCount')!=1
     or original.get('host')!='https://api-contract.weex.com'):
  raise PermissionError('REAL_PILOT_NOT_VERIFIED')
 journal_before=digest(JOURNAL)
 crash_script="""import os
from weex_live_worker import Reader
import live_control
if live_control.state()['mode']!='STOPPED' or live_control.build_errors():
 raise PermissionError('MAIN_NOT_STOPPED')
r=Reader()
order=r.read('get_capi_v3_order',orderId='814587923335741642')
assert str(order.get('orderId'))=='814587923335741642'
os._exit(73)
"""
 child=run_child(crash_script)
 if child.returncode!=73:
  raise RuntimeError('GET_PROCESS_CRASH_NOT_OBSERVED:'+child.stderr[-500:])
 if digest(JOURNAL)!=journal_before:raise RuntimeError('JOURNAL_CHANGED_DURING_CRASH')
 # A second interpreter runs the exact one-shot entry script: it MUST exit
 # before network because the original durable journal already exists.
 no_retry=subprocess.run([PYTHON,str(ROOT/'weex_cross_real_one_shot_pilot_20261109.py')],
   cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=12)
 if (no_retry.returncode!=0 or
     'ONE_SHOT_ALREADY_RESERVED_DO_NOT_RESEND' not in no_retry.stdout
     or digest(JOURNAL)!=journal_before):
  raise RuntimeError('ONE_SHOT_DUPLICATE_GUARD_FAILED')
 # Independent fresh interpreter uses authenticated production GET reads.
 restarted=subprocess.run([PYTHON,str(ROOT/'weex_cross_one_shot_real_independent_audit_20261109.py')],
    cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=35)
 if restarted.returncode:
  raise RuntimeError('RESTARTED_GET_READBACK_FAILED:'+restarted.stderr[-600:])
 latest=json.loads(AUDIT.read_text(encoding='utf-8'))
 ids=('entryOrderId','closeOrderId','stopAlgoId')
 proofs=('entryVerified','reduceOnlyCloseVerified','stopTerminalVerified',
         'accountFlatVerified','cross1xStillConfigured','allIndependentChecksPassed')
 valid=(latest.get('environment')=='WEEX_REAL_ACCOUNT'
        and all(latest.get(k)==original.get(k) for k in ids)
        and all(latest.get(k) is True for k in proofs)
        and latest.get('botMode')=='STOPPED' and latest.get('exchangeWrites')==0
        and digest(JOURNAL)==journal_before)
 report={'checkedAt':datetime.now(timezone.utc).isoformat(),
   'scope':'REAL_EXCHANGE_READBACK_AFTER_CONTROLLED_GET_PROCESS_CRASH',
   'controlledReadProcessExitCode':child.returncode,
   'separateFreshInterpreterVerified':restarted.returncode==0,
   'oneShotAttemptReinvocationRefused':True,
   'durableOrderJournalUnchanged':digest(JOURNAL)==journal_before,
   'exchangeEntryId':original['entryOrderId'],
   'exchangeCloseId':original['closeOrderId'],
   'exchangeStopId':original['stopAlgoId'],
   'liveExchangeReadbackPassed':valid,
   'liveTradingBotCrashDuringOrderCertified':False,
   'liveReleaseCrashGateSatisfied':False,
   'newExchangeWrites':0,
   'mainBotRestarted':False,'pilotCompletedAndAccountFlat':latest['accountFlatVerified']}
 temp=REPORT.with_suffix('.tmp');temp.write_text(json.dumps(report,indent=2)+'\n');os.replace(temp,REPORT)
 print(json.dumps(report))
if __name__=='__main__':go()
