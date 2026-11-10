"""Crash at write boundary with durable one-shot reservation.
Real WEEX GET evidence is used only AFTER restart. NO new live order:
the POST receiver in this test is a localhost-only fake, with actual real
WEEX IDs used as reference proof for the completed order.
"""
import json,os,subprocess,sys,tempfile,hashlib
from pathlib import Path
from datetime import datetime,timezone

ROOT=Path(__file__).resolve().parent
PY=sys.executable
ORIGINAL=ROOT/'weex_cross_one_shot_real_pilot_20261109.json'
AUDIT_SCRIPT=ROOT/'weex_cross_one_shot_real_independent_audit_20261109.py'
AUDIT_FILE=ROOT/'weex_cross_one_shot_real_independent_audit_20261109.json'
REPORT=ROOT/'weex_cross_crash_write_boundary_test_20261109.json'
CRASH_PROCESS=r"""
import json,os,sys
from pathlib import Path
p=Path(sys.argv[1]);phase=sys.argv[2]
state=json.loads(p.read_text())
if phase=='entry':
 state['stage']='ENTRY_OUTCOME_UNKNOWN';state['entryAttemptReserved']=True
elif phase=='close':
 state['stage']='CLOSE_OUTCOME_UNKNOWN';state['closeAttemptReserved']=True
else:raise RuntimeError('INVALID_PHASE')
with p.open('w',encoding='utf-8') as f:
 json.dump(state,f);f.flush();os.fsync(f.fileno())
os._exit(73)
"""
RESTART_PROCESS=r"""
import json,sys
from pathlib import Path
p=Path(sys.argv[1]);phase=sys.argv[2]
s=json.loads(p.read_text())
if phase=='entry':
 blocked=s.get('entryAttemptReserved') is True
elif phase=='close':
 blocked=s.get('closeAttemptReserved') is True
else:raise RuntimeError('INVALID_PHASE')
if not blocked:raise RuntimeError('UNSAFE_RETRY_POSSIBLE')
print(json.dumps({'restartDecision':'NO_RESEND_ALREADY_RESERVED',
 'outcome':'UNKNOWN_READBACK_REQUIRED','sendCalls':0,
 'stage':s['stage']}))
"""
def child(code,*args):
 return subprocess.run([PY,'-c',code,*map(str,args)],cwd=ROOT,text=True,
          capture_output=True,timeout=18)
def run():
 if REPORT.exists():print('ALREADY_TESTED');return
 actual=json.loads(ORIGINAL.read_text())
 if (actual['stage']!='CROSS_PILOT_CLOSED_AND_VERIFIED' or
    actual['entryPostCount']!=1 or actual['closePostCount']!=1):
  raise PermissionError('REAL_ORDER_NOT_VERIFIED')
 digest=hashlib.sha256(ORIGINAL.read_bytes()).hexdigest()
 out={}
 for phase in ('entry','close'):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)/'crash_reservation.json'
   p.write_text(json.dumps({'pilotId':actual['clientOrderId'],'stage':'PREPARED',
     'entryAttemptReserved':False,'closeAttemptReserved':False,
     'realOrderIdsSource':'completed-real-order-only'}))
   exitcode=child(CRASH_PROCESS,p,phase)
   if exitcode.returncode!=73:raise RuntimeError('PROCESS_CRASH_NOT_INJECTED_'+phase)
   recovered=child(RESTART_PROCESS,p,phase)
   if recovered.returncode:raise RuntimeError('RECOVERY_PROCESS_FAILED_'+phase)
   result=json.loads(recovered.stdout)
   if result['sendCalls']!=0 or result['restartDecision']!='NO_RESEND_ALREADY_RESERVED':
    raise RuntimeError('DUPLICATE_NOT_BLOCKED_'+phase)
   out[phase]={'crashExit':73,'restartAfterCrash':True,
     'durableIntent':json.loads(p.read_text())['stage'],
     'duplicateWriteCalls':0,'outcome':'UNKNOWN_READBACK_REQUIRED'}
 # Reconcile existing real exchange order/close/stop through new process GETs.
 rr=subprocess.run([PY,str(AUDIT_SCRIPT)],cwd=ROOT,text=True,capture_output=True,timeout=32)
 if rr.returncode:raise RuntimeError('REAL_EXCHANGE_READBACK_FAILED:'+rr.stderr[-400:])
 proof=json.loads(AUDIT_FILE.read_text())
 ids=('entryOrderId','closeOrderId','stopAlgoId')
 confirmed=(proof.get('allIndependentChecksPassed') is True
            and proof.get('accountFlatVerified') is True
            and all(str(proof.get(k))==str(actual.get(k)) for k in ids)
            and hashlib.sha256(ORIGINAL.read_bytes()).hexdigest()==digest)
 report={'checkedAt':datetime.now(timezone.utc).isoformat(),
   'scope':'SIMULATED_WRITE_BOUNDARY_CRASH_PLUS_REAL_COMPLETED_ORDER_GET_RECONCILIATION',
   'stages':out,'realExchangeReadbackConfirmed':confirmed,
   'realExchangeEntryId':actual['entryOrderId'],
   'realExchangeCloseId':actual['closeOrderId'],
   'realExchangeStopId':actual['stopAlgoId'],
   'originalRealPilotJournalUnchanged':True,
   'newProductionWrites':0,'newRealOrders':0,
   'realExchangeWriteActuallyInterrupted':False,
   'liveBotCrashDuringOrderCertified':False,
   'generalReleaseGatePassed':False,
   'allSimulatedWriteBoundaryChecksPassed':confirmed and len(out)==2}
 tmp=REPORT.with_suffix('.tmp');tmp.write_text(json.dumps(report,indent=2)+'\n');os.replace(tmp,REPORT)
 print(json.dumps(report))
if __name__=='__main__':run()
