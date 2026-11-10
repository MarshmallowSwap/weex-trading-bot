"""Multi-symbol ownership ledger from durable live worker evidence (read-only).

An exchange position is bot-controlled ONLY if the production lifecycle's
active, nonterminal trade has a matching exact position ID and symbol, and
a durable ENTRY write. Unknown or contradictory matches are never adopted.
Never infers manual ownership merely from absence of a bot entry: such rows
are UNATTRIBUTED, observable but not operable by the bot.

This is provenance/classification, not permission to trade; CROSS collateral
constraints remain account-wide.
"""
import json,sqlite3
from contextlib import closing
from pathlib import Path

TERMINAL={'CLOSED','REJECTED','SUPERSEDED'}
SOURCES={'automatic':'BOT_AUTOMATIC','manual_telegram':'BOT_TELEGRAM'}

def _rows(root):
 path=Path(root)/'weex_user_live_lifecycle.sqlite3'
 try:
  with closing(sqlite3.connect('file:'+path.resolve().as_posix()+'?mode=ro',uri=True)) as db:
   db.row_factory=sqlite3.Row;db.execute('PRAGMA query_only=ON')
   trades=[dict(r) for r in db.execute('SELECT id,symbol,state,owned,plan FROM trades_v1').fetchall()]
   writes=[dict(r) for r in db.execute("SELECT trade_id,state FROM writes_v1 WHERE kind='ENTRY'").fetchall()]
  return trades,writes
 except (OSError,sqlite3.Error):
  return None,None

def classify(root,positions,regular,conditional):
 if not all(isinstance(group,list) and all(isinstance(x,dict) for x in group)
            for group in (positions,regular,conditional)):
  raise ValueError('OWNERSHIP_SNAPSHOT_INVALID')
 if any(not x.get('symbol') for group in (positions,regular,conditional) for x in group):
  raise ValueError('OWNERSHIP_SYMBOL_MISSING')
 trades,writes=_rows(root)
 if trades is None:
  return {'status':'JOURNAL_UNAVAILABLE','entryAllowed':False,
   'positions':[{'positionId':str(p.get('id')),'symbol':p.get('symbol'),
                 'owner':'UNVERIFIED'} for p in positions],
   'automaticPositionIds':[],'telegramPositionIds':[],
   'unattributedPositionIds':[],'conflictedPositionIds':[],
   'crossSharedCollateral':True,'allAccountPositions':len(positions)}
 by_trade={}
 for w in writes:by_trade.setdefault(w['trade_id'],[]).append(w['state'])
 candidates={}
 for row in trades:
  if row['state'] in TERMINAL:continue
  try:
   owned=json.loads(row['owned']) if row['owned'] else {}
   plan=json.loads(row['plan']) if row['plan'] else {}
   if not isinstance(owned,dict) or not isinstance(plan,dict):continue
   pid=owned.get('positionId');symbol=row['symbol']
   if pid is None or not symbol:continue
   source=owned.get('entrySource',plan.get('entrySource'))
   label=SOURCES.get(source)
   # An unknown entrySource is NOT silently promoted to 'automatic'.
   if label is None:continue
   if not by_trade.get(row['id']):continue
   candidates.setdefault(str(pid),[]).append((str(symbol),label,str(row['id'])))
  except (TypeError,ValueError,KeyError):continue
 result=[];automatic=[];telegram=[];unattributed=[];conflicts=[]
 seen=set()
 for p in positions:
  pid=str(p.get('id') or '')
  symbol=p['symbol'];possible=candidates.get(pid,[])
  if not pid or pid in seen or len(possible)>1 or (possible and possible[0][0]!=symbol):
   owner='CONFLICT';conflicts.append(pid)
  elif len(possible)==1:
   owner=possible[0][1]
   (automatic if owner=='BOT_AUTOMATIC' else telegram).append(pid)
  else:
   owner='UNATTRIBUTED';unattributed.append(pid)
  seen.add(pid)
  result.append({'positionId':pid,'symbol':symbol,'side':p.get('side'),
    'owner':owner,'tradeId':possible[0][2] if len(possible)==1 and
    owner.startswith('BOT_') else None})
 return {'status':'CONFLICT' if conflicts else 'CLASSIFIED_READONLY',
  'entryAllowed':False,'closeAllowed':False,'crossSharedCollateral':True,
  'allAccountPositions':len(positions),'allAccountRegularOrders':len(regular),
  'allAccountConditionalOrders':len(conditional),
  'automaticPositionIds':automatic,'telegramPositionIds':telegram,
  'unattributedPositionIds':unattributed,'conflictedPositionIds':conflicts,
  'positions':result,'exchangeWrites':0}
