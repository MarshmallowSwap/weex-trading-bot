import json,sqlite3
from pathlib import Path
import live_control
from weex_live_worker import Reader
from weex_trading_modes import get_mode
root=Path(__file__).resolve().parent
p,o,a=Reader(root).account()
g=json.loads((root/'live_release_gate_latest.json').read_text())
with sqlite3.connect('file:'+str((root/'weex_user_live_lifecycle.sqlite3').as_posix())+'?mode=ro',uri=True) as db:
 unknown=db.execute("SELECT kind,state,COUNT(*) FROM writes_v1 WHERE state!='RESPONSE_RECEIVED' GROUP BY kind,state").fetchall()
print(json.dumps({'mode':live_control.state(root)['mode'],'integrity':live_control.build_errors(root),'tradingMode':get_mode(root)['mode'],'positions':len(p),'orders':len(o),'conditional':len(a),'unresolvedWrites':unknown,'gate':g['gate'],'passed':g['passed'],'total':g['total'],'blockers':[k for k,v in g['checks'].items() if not v]}))
