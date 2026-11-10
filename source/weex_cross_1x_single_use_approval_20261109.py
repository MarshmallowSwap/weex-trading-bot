"""Explicit single-use supervised close authorization, fail-closed.

An authorization may be issued only by a separately approved operator flow.
This module never issues approval on its own. It persists one scoped grant and
consumes it atomically; crashes or lost acknowledgements never re-arm it.
"""
import hashlib,json,sqlite3,datetime
from contextlib import contextmanager
from pathlib import Path

def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True)
def fingerprint(scope):return hashlib.sha256(canonical(scope).encode()).hexdigest()
def utc():return datetime.datetime.now(datetime.timezone.utc)
@contextmanager
def connect(path):
 c=sqlite3.connect(str(path),timeout=8,isolation_level=None)
 try:
  c.execute('PRAGMA busy_timeout=8000')
  c.execute('PRAGMA synchronous=FULL')
  c.execute('PRAGMA journal_mode=DELETE')
  c.execute('''CREATE TABLE IF NOT EXISTS cross_close_authorization_v1 (
   digest TEXT PRIMARY KEY,pilot_id TEXT NOT NULL UNIQUE,
   position_id TEXT NOT NULL,approved_at TEXT NOT NULL,
   expires_at TEXT NOT NULL,state TEXT NOT NULL)''')
  yield c
 finally:c.close()
def valid_scope(scope):
 return (isinstance(scope,dict) and set(scope)==
  {'pilotId','entryOrderId','positionId','stopAlgoId','payload'}
  and isinstance(scope['pilotId'],str) and scope['pilotId'].startswith('wxpilot_')
  and all(str(scope[k]).isdecimal() and int(str(scope[k]))>0
    for k in ('entryOrderId','positionId','stopAlgoId'))
  and scope['payload']=={'symbol':'ETHUSDT','positionId':int(scope['positionId'])})
def grant(path,scope,*,approved_by_operator=False,ttl_seconds=120):
 if approved_by_operator is not True:raise PermissionError('OPERATOR_APPROVAL_REQUIRED')
 if not valid_scope(scope) or not 1<=ttl_seconds<=120:raise PermissionError('INVALID_SCOPED_GRANT')
 t=utc();digest=fingerprint(scope)
 with connect(path) as c:
  c.execute('BEGIN IMMEDIATE')
  if c.execute('SELECT 1 FROM cross_close_authorization_v1 WHERE pilot_id=?',(scope['pilotId'],)).fetchone():
   c.rollback();raise PermissionError('PILOT_GRANT_ALREADY_EXISTS')
  c.execute('INSERT INTO cross_close_authorization_v1 VALUES(?,?,?,?,?,?)',
    (digest,scope['pilotId'],scope['positionId'],t.isoformat(),
     (t+datetime.timedelta(seconds=ttl_seconds)).isoformat(),'APPROVED'))
  c.commit()
 return {'digest':digest,'pilotId':scope['pilotId'],'expiresAt':
    (t+datetime.timedelta(seconds=ttl_seconds)).isoformat(),'used':False}
def consume(path,scope):
 if not valid_scope(scope):return False
 digest=fingerprint(scope)
 with connect(path) as c:
  c.execute('BEGIN IMMEDIATE')
  r=c.execute('SELECT state,expires_at FROM cross_close_authorization_v1 WHERE digest=?',(digest,)).fetchone()
  if r is None or r[0]!='APPROVED':
   c.rollback();return False
  try:expires=datetime.datetime.fromisoformat(r[1])
  except (ValueError,TypeError):
   c.rollback();return False
  if expires<=utc():
   c.execute('UPDATE cross_close_authorization_v1 SET state=? WHERE digest=?',('EXPIRED',digest))
   c.commit();return False
  n=c.execute('UPDATE cross_close_authorization_v1 SET state=? WHERE digest=? AND state=?',
    ('CONSUMED',digest,'APPROVED')).rowcount
  c.commit()
  return n==1
class SingleUseApproval:
 def __init__(self,path):self.path=Path(path)
 def __call__(self,scope):return consume(self.path,scope)
