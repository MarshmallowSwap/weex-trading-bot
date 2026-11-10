"""Capture a fresh authenticated, flat WEEX pilot baseline; GET-only.

Do not create trade intents or enable writes. Hash all current account observations;
the baseline is evidence for later pilot attribution, not authorization.
"""
import hashlib,json,os,time
from datetime import datetime,timezone
from pathlib import Path
from weex_live_worker import Reader
import live_control

ROOT=Path(__file__).resolve().parent
def capture(root=ROOT, reader=None):
 root=Path(root)
 if live_control.state(root)['mode']!='STOPPED':
  raise PermissionError('MAIN_BOT_MUST_BE_STOPPED')
 if live_control.build_errors(root):
  raise PermissionError('PRODUCTION_CODE_INTEGRITY_FAILED')
 reader=reader or Reader(root)
 start=time.time()
 positions,regular,conditional=reader.account()
 if not all(isinstance(x,list) for x in (positions,regular,conditional)):
  raise ValueError('ACCOUNT_OBSERVATIONS_INCOMPLETE')
 if positions or regular or conditional:
  raise PermissionError('ACCOUNT_NOT_FLAT')
 if time.time()-start>15:raise ValueError('SNAPSHOT_EXPIRED')
 from weex_existing_account_1x_pilot_audit import journal_inventory
 journal=journal_inventory(root/'weex_isolated_pilot.sqlite3')
 if journal.get('records')!=0 or journal.get('dispatchRows')!=0:
  raise PermissionError('PILOT_JOURNAL_NOT_EMPTY')
 # Retain a contemporaneous verifiable flat snapshot; do not claim that the
 # absence of orders now proves future exclusive ownership.
 report={'checkedAt':datetime.now(timezone.utc).isoformat(),
         'account':'CURRENT_WEEX','snapshotVerified':True,
         'observedAtMs':int(start*1000),
         'positions':positions,'regularOrders':regular,'conditionalOrders':conditional,
         'productionMode':'STOPPED','pilotJournalEmpty':True,
         'canSend':False,'canRetry':False,'exchangeWrites':0}
 canonical=json.dumps(report,sort_keys=True,separators=(',',':')).encode()
 report['snapshotSha256']=hashlib.sha256(canonical).hexdigest()
 path=root/'weex_pilot_flat_baseline_latest.json'
 tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
 os.replace(tmp,path)
 return report
if __name__=='__main__':
 r=capture();print(json.dumps({'checkedAt':r['checkedAt'],'snapshotSha256':r['snapshotSha256'],
 'positions':len(r['positions']),'regularOrders':len(r['regularOrders']),
 'conditionalOrders':len(r['conditionalOrders']),'exchangeWrites':0,'canSend':False}))
