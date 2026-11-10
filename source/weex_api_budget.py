"""WEEX server-derived API quota governor."""
import contextvars,json,math,sqlite3,time,urllib.request,urllib.error,re,logging,io
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlsplit
from email.utils import parsedate_to_datetime

ROOT=Path(__file__).resolve().parent
HOST='api-contract.weex.com'
REFRESH_SECONDS=3600
SAFETY_CEILING=490
# Leave at least 250 WEEX request-weight units for preflight plus independent
# recovery. Only discretionary market-data GETs are deferred; never block
# authenticated position/order/TP reconciliation with this lower-priority cap.
MARKET_DATA_RECOVERY_RESERVE=250
LOW_PRIORITY_MARKET_PATHS=frozenset(('/capi/v3/market/klines',
 '/capi/v3/market/depth','/capi/v3/market/trades',
 '/capi/v3/market/premiumIndex','/capi/v3/market/apiTradingSymbols'))
WEIGHTS={
 '/capi/v3/market/klines':1,'/capi/v3/market/depth':1,'/capi/v3/market/trades':5,
 '/capi/v3/market/exchangeInfo':1,'/capi/v3/market/apiTradingSymbols':5,
 '/capi/v3/market/riskLimits':1,'/capi/v3/market/premiumIndex':1,
 '/capi/v3/account/position/allPosition':10,'/capi/v3/account/balance':5,
 '/capi/v3/account/accountConfig':5,'/capi/v3/account/symbolConfig':5,
 '/capi/v3/account/commissionRate':5,'/capi/v3/openOrders':2,
 '/capi/v3/openAlgoOrders':3,'/capi/v3/trailing/openOrders':2,
 '/capi/v3/order':2,'/capi/v3/userTrades':5,'/capi/v3/allAlgoOrders':5,
 '/capi/v3/order/history':10,'/capi/v3/trailing/historyOrders':10,
}
SETTINGS={'/capi/v3/account/marginType':10,'/capi/v3/account/leverage':10}
PLACEMENTS={'/capi/v3/order','/capi/v3/placeTpSlOrder','/capi/v3/algoOrder'}
_priority=contextvars.ContextVar('weex_recovery_budget',default=False)
_background=contextvars.ContextVar('weex_background_budget',default=False)
class BudgetDeferred(RuntimeError):pass

@contextmanager
def background(*args,**kwargs):
    token=_background.set(True)
    try:yield
    finally:_background.reset(token)
@contextmanager
def recovery():
    token=_priority.set(True)
    try:yield
    finally:_priority.reset(token)

def _seconds(interval,num):
    unit={'SECOND':1,'MINUTE':60,'HOUR':3600,'DAY':86400}.get(str(interval).upper())
    if not unit or type(num) is not int or num<=0:return None
    return unit*num
def _header_seconds(name):
    m=re.search(r'-(\d+)([smhd])$',name.lower())
    if not m:return None
    return int(m.group(1))*{'s':1,'m':60,'h':3600,'d':86400}[m.group(2)]

class Budget:
    def __init__(self,root=ROOT,clock=time.time):self.path=Path(root)/'weex_api_budget.sqlite3';self.clock=clock
    @contextmanager
    def db(self):
        c=sqlite3.connect(self.path,timeout=10)
        try:
            c.executescript('''CREATE TABLE IF NOT EXISTS api_calls_v1(at REAL,weight INTEGER,orders INTEGER,path TEXT);
            CREATE TABLE IF NOT EXISTS api_meta_v1(key TEXT PRIMARY KEY,value REAL);
            CREATE INDEX IF NOT EXISTS api_calls_time_v1 ON api_calls_v1(at);
            CREATE TABLE IF NOT EXISTS api_server_observations_v1(at REAL,status INTEGER,path TEXT,headers TEXT);
            CREATE TABLE IF NOT EXISTS api_limits_v2(kind TEXT,seconds INTEGER,limit_value INTEGER,observed_at REAL,source TEXT,PRIMARY KEY(kind,seconds));
            CREATE TABLE IF NOT EXISTS api_counters_v2(kind TEXT,seconds INTEGER,used REAL,observed_at REAL,PRIMARY KEY(kind,seconds));''')
            with c:yield c
        finally:c.close()
    def install_rate_limits(self,rows,source='exchangeInfo'):
        now=self.clock();parsed=[]
        for r in rows if isinstance(rows,list) else []:
            kind=str(r.get('rateLimitType','')).upper();sec=_seconds(r.get('interval'),r.get('intervalNum'));limit=r.get('limit')
            if kind not in ('REQUEST_WEIGHT','ORDERS') or not sec or type(limit) is not int or limit<=0:continue
            parsed.append((kind,sec,min(limit,SAFETY_CEILING),now,source))
        if not parsed:raise ValueError('WEEX_RATE_LIMITS_INVALID')
        with self.db() as c:
            c.execute('BEGIN IMMEDIATE');c.execute("DELETE FROM api_limits_v2 WHERE source='exchangeInfo'")
            c.executemany('INSERT OR REPLACE INTO api_limits_v2 VALUES(?,?,?,?,?)',parsed)
            c.execute("INSERT OR REPLACE INTO api_meta_v1 VALUES('rate_limits_at',?)",(now,))
    def _limits(self):
        with self.db() as c:
            return c.execute('SELECT kind,seconds,limit_value,observed_at,source FROM api_limits_v2').fetchall()
    def ensure_limits(self,timeout=10):
        now=self.clock()
        with self.db() as c:
            last=c.execute("SELECT value FROM api_meta_v1 WHERE key='rate_limits_at'").fetchone()
            has=c.execute('SELECT COUNT(*) FROM api_limits_v2').fetchone()[0]
            refreshing=c.execute("SELECT value FROM api_meta_v1 WHERE key='rate_limits_refreshing'").fetchone()
            if has and last and now-last[0]<REFRESH_SECONDS:return
            if refreshing and now-refreshing[0]<30:raise BudgetDeferred('WEEX_RATE_LIMIT_REFRESH_IN_PROGRESS')
            c.execute("INSERT OR REPLACE INTO api_meta_v1 VALUES('rate_limits_refreshing',?)",(now,))
        url='https://'+HOST+'/capi/v3/market/exchangeInfo'
        self.reserve('GET',url,bootstrap=True)
        try:
            r=urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'WEEX-RateLimit-Guard/1'}),timeout=timeout)
            raw=r.read(16*1024*1024+1);headers=r.headers;status=getattr(r,'status',200);r.close()
            if len(raw)>16*1024*1024:raise ValueError('WEEX_EXCHANGE_INFO_TOO_LARGE')
            body=json.loads(raw);self.observe(status,headers,url)
            self.install_rate_limits(body.get('rateLimits'))
        except Exception:
            with self.db() as c:c.execute("DELETE FROM api_meta_v1 WHERE key='rate_limits_refreshing'")
            # A valid cached policy remains usable for a bounded outage; no cache means fail closed.
            if not self._limits():raise BudgetDeferred('WEEX_RATE_LIMITS_UNAVAILABLE')
            raise
        with self.db() as c:c.execute("DELETE FROM api_meta_v1 WHERE key='rate_limits_refreshing'")
    def _usage(self,c,kind,seconds,now):
        col='weight' if kind=='REQUEST_WEIGHT' else 'orders'
        local=c.execute(f'SELECT COALESCE(SUM({col}),0) FROM api_calls_v1 WHERE at>?',(now-seconds,)).fetchone()[0]
        snap=c.execute('SELECT used,observed_at FROM api_counters_v2 WHERE kind=? AND seconds=?',(kind,seconds)).fetchone()
        if snap and now-snap[1]<seconds:
            after=c.execute(f'SELECT COALESCE(SUM({col}),0) FROM api_calls_v1 WHERE at>? AND at>?',(max(now-seconds,snap[1]),snap[1])).fetchone()[0]
            return max(local,snap[0]+after)
        return local
    def reserve(self,method,url,*,critical=None,bootstrap=False):
        parsed=urlsplit(url)
        if parsed.scheme!='https' or parsed.netloc!=HOST or parsed.fragment:raise PermissionError('BUDGET_DESTINATION_NOT_ALLOWED')
        path=parsed.path;orders=0
        if method=='GET' and path in WEIGHTS:weight=WEIGHTS[path]
        elif method=='POST' and path in SETTINGS:weight=SETTINGS[path]
        elif method=='POST' and path in PLACEMENTS:weight=0;orders=1
        elif method=='DELETE' and path in ('/capi/v3/order','/capi/v3/algoOrder'):weight=1
        else:raise BudgetDeferred('UNCLASSIFIED_API_WEIGHT')
        with self.db() as c:
            c.execute('BEGIN IMMEDIATE');now=self.clock()
            last=c.execute("SELECT value FROM api_meta_v1 WHERE key='clock'").fetchone()
            if last and now<last[0]:raise BudgetDeferred('SYSTEM_CLOCK_MOVED_BACKWARD')
            pause=c.execute("SELECT value FROM api_meta_v1 WHERE key='pause'").fetchone()
            if pause and pause[0]>now:raise BudgetDeferred('WEEX_SHARED_COOLDOWN')
            limits=c.execute('SELECT kind,seconds,limit_value FROM api_limits_v2').fetchall()
            if not limits and not bootstrap:raise BudgetDeferred('WEEX_RATE_LIMITS_UNAVAILABLE')
            if not limits and bootstrap:
                prev=c.execute("SELECT value FROM api_meta_v1 WHERE key='exchange_info_bootstrap'").fetchone()
                if prev and now-prev[0]<10:raise BudgetDeferred('WEEX_RATE_LIMITS_REFRESH_IN_PROGRESS')
                c.execute("INSERT OR REPLACE INTO api_meta_v1 VALUES('exchange_info_bootstrap',?)",(now,))
            if limits:
                # Atomic admission of discretionary public traffic under the
                # same SQLite lock as real orders and critical GETs.
                if method=='GET' and path in LOW_PRIORITY_MARKET_PATHS:
                    long_windows=[(sec,limit) for kind,sec,limit in limits
                                  if kind=='REQUEST_WEIGHT' and sec>=600]
                    if not long_windows:
                        raise BudgetDeferred('MARKET_RECOVERY_RESERVE_UNVERIFIED')
                    for sec,limit in long_windows:
                        used=self._usage(c,'REQUEST_WEIGHT',sec,now)
                        if used+weight>min(limit,SAFETY_CEILING)-MARKET_DATA_RECOVERY_RESERVE:
                            raise BudgetDeferred('MARKET_YIELDS_TO_RECOVERY_API_RESERVE')
                for kind,sec,limit in limits:
                    amount=weight if kind=='REQUEST_WEIGHT' else orders
                    if not amount:continue
                    used=self._usage(c,kind,sec,now)
                    if used+amount>limit:raise BudgetDeferred('WAIT_API_'+kind+'_BUDGET')
            c.execute('DELETE FROM api_calls_v1 WHERE at<=?',(now-86400,))
            c.execute('INSERT INTO api_calls_v1 VALUES(?,?,?,?)',(now,weight,orders,path))
            c.execute("INSERT OR REPLACE INTO api_meta_v1 VALUES('clock',?)",(now,))
        return weight
    def observe(self,status,headers,path=None):
        headers={str(k).lower():str(v) for k,v in (headers or {}).items()};now=self.clock()
        safe={k:v[:128] for k,v in headers.items() if re.fullmatch(r'(?:x-(?:used-weight|remaining-weight|order-remaining|order-count)-[0-9]+[smhd]|retry-after|date)',k)}
        try:
            with self.db() as c:
                c.execute('INSERT INTO api_server_observations_v1 VALUES(?,?,?,?)',(now,status,urlsplit(path).path if path else None,json.dumps(safe)))
                for kind,prefix_used,prefix_remaining in (('REQUEST_WEIGHT','x-used-weight-','x-remaining-weight-'),('ORDERS','x-order-count-','x-order-remaining-')):
                    for key,raw in safe.items():
                        if not key.startswith(prefix_used):continue
                        sec=_header_seconds(key);rem_key=prefix_remaining+key[len(prefix_used):]
                        if not sec or rem_key not in safe:continue
                        try:used=float(raw);remaining=float(safe[rem_key])
                        except ValueError:continue
                        limit=max(0,int(used+remaining))
                        if limit:
                            c.execute('INSERT OR REPLACE INTO api_limits_v2 VALUES(?,?,?,?,?)',(kind,sec,min(limit,SAFETY_CEILING),now,'response-header'))
                            c.execute('INSERT OR REPLACE INTO api_counters_v2 VALUES(?,?,?,?)',(kind,sec,used,now))
                if status in (418,429):
                    raw=headers.get('retry-after','10')
                    try:delay=float(raw)
                    except ValueError:
                        try:delay=parsedate_to_datetime(raw).timestamp()-now
                        except (ValueError,TypeError,OverflowError):delay=10
                    if not math.isfinite(delay):delay=10
                    c.execute("INSERT INTO api_meta_v1 VALUES('pause',?) ON CONFLICT(key) DO UPDATE SET value=MAX(value,excluded.value)",(now+max(10,delay),))
        except Exception as exc:logging.warning('WEEX rate-limit telemetry unavailable (%s)',type(exc).__name__)
    def used(self):
        now=self.clock()
        with self.db() as c:
            weight=c.execute('SELECT COALESCE(SUM(weight),0) FROM api_calls_v1 WHERE at>?',(now-600,)).fetchone()[0]
            orders=c.execute('SELECT COALESCE(SUM(orders),0) FROM api_calls_v1 WHERE at>?',(now-60,)).fetchone()[0]
            pause=c.execute("SELECT value FROM api_meta_v1 WHERE key='pause'").fetchone()
            limits=[{'type':k,'windowSeconds':s,'limit':v,'observedAt':at,'source':src} for k,s,v,at,src in c.execute('SELECT kind,seconds,limit_value,observed_at,source FROM api_limits_v2')]
        return {'weight':weight,'orders':orders,'limits':limits,'mode':'WEEX_SERVER_LIMITS','pauseUntil':pause[0] if pause else 0}
    def require_entry_headroom(self):
        self.ensure_limits()
        if self.used()['pauseUntil']>self.clock():raise BudgetDeferred('WAIT_API_BUDGET_BEFORE_NEW_ENTRY')
    def require_supervised_recovery_headroom(self, *, recovery_weight=150, preflight_weight=0):
        """Fail-closed admission using WEEX's per-window limits and observed counters.

        Recovery reserve covers repeated independent account/order/stop/fills
        readbacks and one emergency close; preflight reserve is only applied
        before capture. This is not a reservation of future API quota: every
        actual API call is still governed independently by reserve().
        """
        if (type(recovery_weight) is not int or recovery_weight<100
                or type(preflight_weight) is not int or preflight_weight<0):
            raise BudgetDeferred('INVALID_SUPERVISED_API_RESERVE')
        self.ensure_limits()
        with self.db() as c:
            c.execute('BEGIN IMMEDIATE')
            now=self.clock()
            pause=c.execute("SELECT value FROM api_meta_v1 WHERE key='pause'").fetchone()
            if pause and pause[0]>now:
                raise BudgetDeferred('WAIT_API_BUDGET_BEFORE_NEW_ENTRY')
            rules=c.execute('SELECT kind,seconds,limit_value,observed_at FROM api_limits_v2').fetchall()
            if not rules or not any(k=='REQUEST_WEIGHT' and s>=600 for k,s,_,_ in rules):
                raise BudgetDeferred('RECOVERY_LONG_WINDOW_LIMIT_UNVERIFIED')
            if not any(k=='ORDERS' for k,_,_,_ in rules):
                raise BudgetDeferred('RECOVERY_ORDER_WINDOW_LIMIT_UNVERIFIED')
            for kind,sec,limit,observed in rules:
                if now-observed>REFRESH_SECONDS or now<observed-5:
                    raise BudgetDeferred('RECOVERY_API_LIMITS_STALE')
                needed=(recovery_weight+preflight_weight) if kind=='REQUEST_WEIGHT' and sec>=600 else (
                    min(25,recovery_weight) if kind=='REQUEST_WEIGHT' else 1)
                used=self._usage(c,kind,sec,now)
                if used+needed>limit:
                    raise BudgetDeferred('RECOVERY_API_HEADROOM_REQUIRED')
        return True
    def ready_at(self,weight=1,headroom=0,now=None):
        now=self.clock() if now is None else now;target=weight+headroom;ready=now
        with self.db() as c:
            rules=c.execute('SELECT kind,seconds,limit_value FROM api_limits_v2').fetchall()
            for kind,sec,limit in rules:
                amount=target if kind=='REQUEST_WEIGHT' else 0
                if not amount:continue
                rows=c.execute('SELECT at,weight FROM api_calls_v1 WHERE at>? ORDER BY at',(now-sec,)).fetchall();used=sum(x[1] for x in rows)
                snap=c.execute('SELECT used,observed_at FROM api_counters_v2 WHERE kind=? AND seconds=?',(kind,sec)).fetchone()
                if snap and now-snap[1]<sec:used=max(used,snap[0])
                if used+amount>limit:
                    if snap and now-snap[1]<sec:ready=max(ready,snap[1]+sec)
                    for at,w in rows:
                        used-=w
                        if used+amount<=limit:
                            ready=max(ready,at+sec);break
        return ready

def budget():return Budget()
def open_url(request,timeout=12):
    url=request if isinstance(request,str) else request.full_url;method='GET' if isinstance(request,str) else request.get_method()
    if method!='GET':raise PermissionError('GET_ONLY_BUDGET_ADAPTER')
    b=budget();path=urlsplit(url).path
    if path!='/capi/v3/market/exchangeInfo':b.ensure_limits(timeout=min(timeout,10))
    b.reserve(method,url,bootstrap=path.endswith('/exchangeInfo'))
    try:
        response=urllib.request.urlopen(request,timeout=timeout);headers=response.headers;status=getattr(response,'status',200);b.observe(status,headers,url)
        if path.endswith('/exchangeInfo'):
            raw=response.read(16*1024*1024+1);response.close()
            if len(raw)>16*1024*1024:raise ValueError('WEEX_EXCHANGE_INFO_TOO_LARGE')
            b.install_rate_limits(json.loads(raw).get('rateLimits'))
            wrapped=io.BytesIO(raw);wrapped.headers=headers;wrapped.status=status;return wrapped
        return response
    except urllib.error.HTTPError as exc:b.observe(exc.code,exc.headers,url);raise
def request(session,method,url,**kwargs):
    b=budget();path=urlsplit(url).path
    if path!='/capi/v3/market/exchangeInfo':b.ensure_limits(timeout=min(kwargs.get('timeout',10),10))
    b.reserve(method,url,bootstrap=path.endswith('/exchangeInfo'))
    response=session.request(method=method,url=url,**kwargs);b.observe(response.status_code,response.headers,url)
    if path.endswith('/exchangeInfo') and response.ok:b.install_rate_limits(response.json().get('rateLimits'))
    return response
