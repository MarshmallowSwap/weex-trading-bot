"""Read-only audit of unresolved WEEX live lifecycle records; no modifications."""
import sqlite3,json
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parent
def audit():
    from weex_live_worker import Reader
    positions,regular,algos=Reader(ROOT).account()
    with sqlite3.connect('file:'+str((ROOT/'weex_user_live_lifecycle.sqlite3').as_posix())+'?mode=ro',uri=True) as db:
        db.row_factory=sqlite3.Row
        rows=db.execute("SELECT id,symbol,state,updated FROM trades_v1 WHERE state NOT IN ('CLOSED','REJECTED','SUPERSEDED')").fetchall()
        pending=[]
        for r in rows:
            writes=[dict(x) for x in db.execute("SELECT kind,state FROM writes_v1 WHERE trade_id=?",(r['id'],))]
            sym=r['symbol']
            pending.append({'tradeId':r['id'],'symbol':sym,'state':r['state'],
               'currentlyExposed':any(p.get('symbol')==sym for p in positions),
               'currentRegularCount':sum(o.get('symbol')==sym for o in regular),
               'currentAlgoCount':sum(o.get('symbol')==sym for o in algos),
               'writeStates':writes,'mayAutoResolve':False,'canResubmit':False})
    return {'checkedAt':datetime.now(timezone.utc).isoformat(),'source':'LIVE_READ_ONLY',
      'openPositionSymbols':sorted({p.get('symbol') for p in positions}),
      'unresolvedCount':len(pending),'unresolved':pending,
      'automaticClearAllowed':False,'liveWrites':0,'modeChanged':False}
if __name__=='__main__':
 print(json.dumps(audit()))
