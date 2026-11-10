"""Telegram-owned authorization bridge for supervised ETH CROSS 1x CLOSE only.

Runs inside commands.py getUpdates authenticated Telegram polling path.
No API writes. No operator challenge can be issued without fresh exchange
position+native stop corroboration and a matching persisted pilot record.
"""
import hashlib,json,secrets,sqlite3,time
from pathlib import Path
from contextlib import contextmanager
from weex_cross_1x_single_use_approval_20261109 import grant,fingerprint,valid_scope
from weex_cross_1x_emergency_readiness_20261109 import assess
import live_control

FILENAME='weex_cross_1x_pending_supervised_pilot.json'
AUTH='weex_cross_1x_operator_approval.sqlite3'
@contextmanager
def connection(root):
 c=sqlite3.connect(str(Path(root)/AUTH),timeout=8,isolation_level=None)
 try:
  c.execute('PRAGMA busy_timeout=8000')
  c.execute('PRAGMA synchronous=FULL')
  c.execute('''CREATE TABLE IF NOT EXISTS cross_close_challenges_v1 (
   nonce TEXT PRIMARY KEY,pilot_id TEXT NOT NULL,scope_hash TEXT NOT NULL,
   user_id TEXT NOT NULL,chat_id TEXT NOT NULL,expires REAL NOT NULL,
   state TEXT NOT NULL)''')
  yield c
 finally:c.close()
def current_scope(root,reader=None):
 """Re-read account and order: never trust a stored flag or old screenshot."""
 from weex_live_worker import Reader
 root=Path(root)
 if live_control.state(root)['mode']!='STOPPED' or live_control.build_errors(root):
  raise PermissionError('BOT_MUST_BE_STOPPED_WITH_VALID_INTEGRITY')
 path=root/FILENAME
 if not path.is_file():raise PermissionError('NO_PENDING_CROSS_PILOT')
 data=json.loads(path.read_text(encoding='utf-8'))
 if not isinstance(data,dict) or set(data)!={'intent','entryOrderId','stopAlgoId','positionId'}:
  raise PermissionError('INVALID_PILOT_RECORD')
 intent=data['intent']
 if not isinstance(intent,dict) or not isinstance(intent.get('newClientOrderId'),str):
  raise PermissionError('INVALID_PILOT_INTENT')
 if not all(str(data[k]).isdecimal() for k in ('entryOrderId','stopAlgoId','positionId')):
  raise PermissionError('INVALID_PILOT_IDENTITIES')
 reader=reader or Reader(root)
 entry=reader.read('get_capi_v3_order',orderId=str(data['entryOrderId']))
 positions,regular,conditional=reader.account()
 cfg=reader.read('get_capi_v3_account_symbolConfig',symbol='ETHUSDT')
 if not (isinstance(cfg,list) and len(cfg)==1
   and cfg[0].get('marginType') in ('CROSS','CROSSED')
   and str(cfg[0].get('crossLeverage'))=='1'):
  raise PermissionError('EXCHANGE_CROSS_1X_NOT_CONFIRMED')
 result=assess(intent=intent,entry=entry,positions=positions,regular_orders=regular,
   conditional=conditional,exchange_cross_leverage='1')
 if result.get('readyForSupervisedClose') is not True:
  raise PermissionError('CROSS_CLOSE_READINESS_FAILED_'+str(result.get('reason')))
 if (result['entryOrderId']!=str(data['entryOrderId']) or
   result['positionId']!=str(data['positionId']) or
   result['stopAlgoId']!=str(data['stopAlgoId'])):
  raise PermissionError('PILOT_JOURNAL_NOT_EXACT')
 scope={'pilotId':intent['newClientOrderId'],'entryOrderId':result['entryOrderId'],
  'positionId':result['positionId'],'stopAlgoId':result['stopAlgoId'],
  'payload':result['closePayloadPreview']}
 if not valid_scope(scope):raise PermissionError('INVALID_CROSS_CLOSE_SCOPE')
 return scope
def challenge(root,user,chat,*,reader=None,now=None):
 scope=current_scope(root,reader)
 t=time.time() if now is None else now
 nonce=secrets.token_urlsafe(14)
 with connection(root) as c:
  c.execute('BEGIN IMMEDIATE')
  if c.execute('SELECT 1 FROM cross_close_challenges_v1 WHERE pilot_id=? AND state IN (?,?)',
   (scope['pilotId'],'PENDING','CONFIRMED')).fetchone():
   c.rollback();raise PermissionError('CHALLENGE_ALREADY_EXISTS_FOR_PILOT')
  c.execute('''INSERT INTO cross_close_challenges_v1 VALUES (?,?,?,?,?,?,?)''',
   (nonce,scope['pilotId'],fingerprint(scope),str(user),str(chat),t+120,'PENDING'))
  c.commit()
 return {'nonce':nonce,'scope':scope,'expiresAt':t+120,'exchangeWrites':0}
def confirm(root,nonce,user,chat,*,reader=None,now=None):
 t=time.time() if now is None else now
 if not isinstance(nonce,str) or len(nonce)>60 or not nonce.isascii():return False
 # Independently compare the still-open position before granting a live
 # close. An error leaves challenge pending, but its expiration still holds.
 try:scope=current_scope(root,reader)
 except Exception:return False
 with connection(root) as c:
  c.execute('BEGIN IMMEDIATE')
  row=c.execute('''SELECT pilot_id,scope_hash,user_id,chat_id,expires,state
   FROM cross_close_challenges_v1 WHERE nonce=?''',(nonce,)).fetchone()
  if (not row or row[5]!='PENDING' or row[4]<t or
      row[2]!=str(user) or row[3]!=str(chat) or
      row[0]!=scope['pilotId'] or row[1]!=fingerprint(scope)):
   c.rollback();return False
  c.execute('UPDATE cross_close_challenges_v1 SET state=? WHERE nonce=?',('CONFIRMED',nonce))
  c.commit()
 try:
  grant(Path(root)/AUTH,scope,approved_by_operator=True,ttl_seconds=120)
 except Exception:return False
 return True
