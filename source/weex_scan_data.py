"""Public GET-only scanner budget and cache of completed candles; no credentials."""
import json,sqlite3,threading,time,urllib.request,urllib.parse,urllib.error
from weex_api_budget import open_url
from datetime import datetime,timezone
from pathlib import Path
from contextlib import contextmanager
from decimal import Decimal,InvalidOperation

HOST='https://api-contract.weex.com'
PATHS={'/capi/v3/market/klines','/capi/v3/market/depth','/capi/v3/market/exchangeInfo','/capi/v3/market/apiTradingSymbols','/capi/v3/market/trades'}
class ScanBudgetExceeded(RuntimeError):pass
class ScanThrottled(RuntimeError):pass
# Preserve substantial request capacity for live account/recovery GETs.
# Scanner observations beyond this bound are unavailable, never fabricated.
MAX_PUBLIC_SCANNER_REQUESTS_PER_CYCLE=80
# Keep 250 of the 490-weight long window for account/recovery operations.
MAX_SHARED_API_WEIGHT_BEFORE_SCANNER_PAUSE=240

def merged_bar(parts,period):
    """Exact OHLCV aggregation; no synthetic values for absent five-minute bars."""
    if len(parts)!=period//300000:raise ValueError('INCOMPLETE_FIVE_MINUTE_GROUP')
    start=int(parts[0][0])
    if start%period:raise ValueError('UNALIGNED_CANDLE_GROUP')
    for i,row in enumerate(parts):
        if len(row)!=11 or int(row[0])!=start+i*300000 or int(row[6])!=int(row[0])+300000:
            raise ValueError('INVALID_FIVE_MINUTE_BOUNDARIES')
        values=[Decimal(str(x)) for x in row]
        if not all(x.is_finite() for x in values) or any(values[j]<=0 for j in (1,2,3,4)) or any(values[j]<0 for j in (5,7,8,9,10)):
            raise ValueError('INVALID_CANDLE_VALUES')
        if not values[3]<=min(values[1],values[4])<=max(values[1],values[4])<=values[2] or values[8]!=int(values[8]):
            raise ValueError('INVALID_OHLC_OR_TRADE_COUNT')
    return [start,parts[0][1],str(max(Decimal(x[2]) for x in parts)),str(min(Decimal(x[3]) for x in parts)),parts[-1][4],
            str(sum(Decimal(x[5]) for x in parts)),start+period,str(sum(Decimal(x[7]) for x in parts)),
            sum(int(x[8]) for x in parts),str(sum(Decimal(x[9]) for x in parts)),str(sum(Decimal(x[10]) for x in parts))]

def derive_higher(old,lower,period,expected,anchor_ms,limit):
    """Extend the native rolling history only after an exact overlapping-bar check."""
    try:
        if len(old)!=limit-1 or len(old)<35 or not lower:return None
        if any(len(row)!=11 or int(row[0])%period or int(row[6])!=int(row[0])+period or int(row[6])>=anchor_ms for row in old):return None
        if any(int(b[0])-int(a[0])!=period for a,b in zip(old,old[1:])):return None
        if any(len(row)!=11 or int(row[6])>=anchor_ms for row in lower):return None
        if any(int(b[0])-int(a[0])!=300000 for a,b in zip(lower,lower[1:])):return None
        by_time={int(row[0]):row for row in lower}
        def group(start):return [by_time[t] for t in range(start,start+period,300000)]
        overlap=merged_bar(group(int(old[-1][0])),period)
        if any(Decimal(str(a))!=Decimal(str(b)) for a,b in zip(overlap,old[-1])):return None
        if int(old[-1][0])>=expected:return None
        additions=[merged_bar(group(start),period) for start in range(int(old[-1][0])+period,expected+1,period)]
        rows=(old+additions)[-(limit-1):]
        if len(rows)!=limit-1 or int(rows[-1][0])!=expected or int(rows[-1][6])>=anchor_ms:return None
        return rows
    except (ValueError,TypeError,KeyError,IndexError,InvalidOperation):return None

class PublicData:
    def __init__(self,root,*,deadline_seconds=180,clock=time.time,opener=open_url):
        self.root=Path(root);self.clock=clock;self.anchor=clock();self.deadline=self.anchor+deadline_seconds
        self.opener=opener;self.lock=threading.Lock();self.requests=0;self.cache_hits=0
        self.derived_frames=0;self.derived_bars=0
        self.throttled=False;self.headers={};self.database=self.root/'weex_scan_data.sqlite3'
        with self.db() as c:
            c.executescript('CREATE TABLE IF NOT EXISTS calls(at REAL); CREATE TABLE IF NOT EXISTS pause(id INTEGER PRIMARY KEY, until REAL); CREATE TABLE IF NOT EXISTS candles(symbol TEXT,tf TEXT,last_open INTEGER,rows TEXT,PRIMARY KEY(symbol,tf));')
    @contextmanager
    def db(self):
        connection=sqlite3.connect(self.database,timeout=10)
        try:
            with connection:yield connection
        finally:connection.close()
    def reserve(self):
        # Bound the scanner before the shared governor is exhausted.
        # Preserve authenticated account/position recovery GET capacity.
        with self.lock:
            if self.clock()>=self.deadline:raise ScanBudgetExceeded('SCAN_DEADLINE')
            if self.requests>=MAX_PUBLIC_SCANNER_REQUESTS_PER_CYCLE:
                raise ScanBudgetExceeded('SCAN_RECOVERY_API_HEADROOM_RESERVED')
            # Shared quota guard: all scanner instances see the same actual
            # 10-minute API weight, including other independent diagnostics.
            from weex_api_budget import Budget
            used=Budget(self.root).used()['weight']
            if used>=MAX_SHARED_API_WEIGHT_BEFORE_SCANNER_PAUSE:
                raise ScanBudgetExceeded('SHARED_RECOVERY_API_HEADROOM_RESERVED')
            self.requests+=1
    def open(self,request,timeout=12):
        url=request if isinstance(request,str) else request.full_url
        parsed=urllib.parse.urlparse(url)
        method='GET' if isinstance(request,str) else request.get_method()
        if parsed.scheme!='https' or parsed.netloc!='api-contract.weex.com' or parsed.path not in PATHS or method!='GET':
            raise PermissionError('PUBLIC_SCANNER_GET_ONLY')
        def attempt(request,timeout):
            self.reserve()
            return self.opener(request,timeout=timeout)
        try:
            from weex_read_recovery import read_public
            response=read_public(request,attempt,root=self.root,deadline=self.deadline,timeout=min(timeout,12),clock=self.clock)
            self.headers={k:v for k,v in response.headers.items() if k.lower().startswith(('x-used-weight','x-remaining-weight'))}
            return response
        except urllib.error.HTTPError as exc:
            if exc.code in (418,429):
                try:retry=float(exc.headers.get('Retry-After','600'))
                except (ValueError,TypeError):retry=600
                with self.lock,self.db() as c:
                    c.execute('INSERT OR REPLACE INTO pause VALUES(1,?)',(self.clock()+max(600,retry),))
                self.throttled=True
                raise ScanThrottled('WEEX_RATE_LIMIT_NO_RETRY') from None
            raise
    def get(self,path,**params):
        url=HOST+path+'?'+urllib.parse.urlencode(params)
        with self.open(urllib.request.Request(url,headers={'User-Agent':'WEEX-Full-Scan/1'})) as response:
            return json.load(response)
    def candles(self,symbol,tf,limit=85):
        period={'5m':300000,'15m':900000,'1h':3600000}[tf]
        expected=int(self.anchor*1000)//period*period-period
        with self.lock,self.db() as c:
            cached=c.execute('SELECT last_open,rows FROM candles WHERE symbol=? AND tf=?',(symbol,tf)).fetchone()
            if cached and cached[0]==expected:
                self.cache_hits+=1;return json.loads(cached[1])
        if tf in ('15m','1h') and cached:
            with self.lock,self.db() as c:
                lower=c.execute("SELECT rows FROM candles WHERE symbol=? AND tf='5m'",(symbol,)).fetchone()
            if lower:
                derived=derive_higher(json.loads(cached[1]),json.loads(lower[0]),period,expected,int(self.anchor*1000),limit)
                if derived is not None:
                    with self.lock,self.db() as c:
                        c.execute('INSERT OR REPLACE INTO candles VALUES(?,?,?,?)',(symbol,tf,expected,json.dumps(derived)))
                        self.derived_frames+=1;self.derived_bars+=(expected-cached[0])//period
                    return derived
        raw=self.get('/capi/v3/market/klines',symbol=symbol,interval=tf,limit=limit)
        if not isinstance(raw,list):raise ValueError('INVALID_CANDLES')
        rows=sorted([r for r in raw if int(r[0])<=expected and int(r[6])<int(self.anchor*1000)],key=lambda r:int(r[0]))
        if len(rows)<35 or int(rows[-1][0])!=expected:raise ValueError('LATEST_CLOSED_CANDLE_MISSING')
        if len({int(r[0]) for r in rows})!=len(rows) or any(int(b[0])-int(a[0])!=period for a,b in zip(rows,rows[1:])):
            raise ValueError('CANDLE_GAP_OR_DUPLICATE')
        with self.lock,self.db() as c:
            c.execute('INSERT OR REPLACE INTO candles VALUES(?,?,?,?)',(symbol,tf,expected,json.dumps(rows)))
        return rows
    def stats(self):
        return {'requestsThisCycle':self.requests,'candleCacheHits':self.cache_hits,
                'higherTimeframesFrom5m':self.derived_frames,'higherBarsFrom5m':self.derived_bars,
                'globalBudgetModule':'weex_api_budget','budgetMode':'WEEX_SERVER_LIMITS',
                'throttled':self.throttled,'lastWeightHeaders':self.headers}
