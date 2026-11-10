import sqlite3,json
from pathlib import Path
p=Path(__file__).with_name('weex_user_live_lifecycle.sqlite3')
conn=sqlite3.connect('file:'+p.resolve().as_posix()+'?mode=ro',uri=True)
conn.row_factory=sqlite3.Row
data=[]
for x in conn.execute("SELECT symbol,state,detail FROM trades_v1 WHERE symbol IN ('LTCUSDT','QNTUSDT')"):
 detail=json.loads(x['detail'] or '{}')
 data.append({'symbol':x['symbol'],'state':x['state'],
              'detailKeys':sorted(detail),'resolution':detail.get('resolution'),
              'exitOrderIds':detail.get('exitOrderIds'),'netBeforeFunding':detail.get('realizedNetBeforeFundingUSDT')})
print('TARGETS',json.dumps(data))
print('UNRESOLVED',[(x['symbol'],x['state']) for x in conn.execute("SELECT symbol,state FROM trades_v1 WHERE state NOT IN ('CLOSED','REJECTED','SUPERSEDED')")])
conn.close()
