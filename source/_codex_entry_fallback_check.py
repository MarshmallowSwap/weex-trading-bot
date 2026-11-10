import json,sqlite3,sys
from pathlib import Path
sys.path.insert(0,r'D:\FUNDSHOT\weex_alerts')
from weex_live_worker import Lifecycle
db=Path(r'D:\FUNDSHOT\weex_alerts\weex_user_live_lifecycle.sqlite3')
c=sqlite3.connect(f'file:{db}?mode=ro',uri=True);c.row_factory=sqlite3.Row
row=c.execute("select id,symbol,plan,owned from trades_v1 where symbol='EGLDUSDT'").fetchone();c.close()
item={k:row[k] for k in ('id','symbol')};item['plan']=json.loads(row['plan']);item['owned']=json.loads(row['owned'])
proof=item['owned']['entryFillEvidence'];order=proof['rawOrder'];engine=object.__new__(Lifecycle)
partial=proof['fills'][:1]
result,_=engine.entry_fills(item,order,partial,[])
assert str(result[0])==item['owned']['quantity']
assert str(result[1])==item['owned']['actualEntryCostUSDT']
assert str(result[2])==item['owned']['actualEntryFeesUSDT']
bad=[dict(partial[0])];bad[0]['price']=str(float(bad[0]['price'])+0.001)
try:engine.entry_fills(item,order,bad,[])
except ValueError:pass
else:raise AssertionError('conflicting fill was accepted')
print('partial-history reconciliation OK; altered fill rejected; no network or DB writes')
