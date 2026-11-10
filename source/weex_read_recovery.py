"""Finite retries for public GETs only. Never used by order transports."""
import socket,ssl,time,urllib.error,io
from urllib.parse import urlsplit
from weex_api_budget import BudgetDeferred,WEIGHTS
from weex_incidents import Store,budget_ready_at

def transient(exc):
    if isinstance(exc,urllib.error.HTTPError):return exc.code in (500,502,503,504)
    if isinstance(exc,ssl.SSLError):return False
    if isinstance(exc,urllib.error.URLError):return transient(exc.reason)
    return isinstance(exc,(TimeoutError,ConnectionError,socket.gaierror))

def read_public(request,opener,*,root,deadline,timeout=12,clock=time.time,sleep=time.sleep):
    url=request if isinstance(request,str) else request.full_url
    method='GET' if isinstance(request,str) else request.get_method();parsed=urlsplit(url)
    if method!='GET' or parsed.scheme!='https' or parsed.netloc!='api-contract.weex.com' or not parsed.path.startswith('/capi/v3/market/') or parsed.path not in WEIGHTS:
        raise PermissionError('PUBLIC_GET_RECOVERY_ONLY')
    store=Store(root,clock);key='public:connection';attempt=0
    while True:
        if clock()>=deadline:raise BudgetDeferred('PUBLIC_RECOVERY_DEADLINE')
        active=store.get(key)
        if active and active['state']!='RESOLVED':
            delay=max(0,active['next_at']-clock())
            if active['state']=='ATTENTION' or clock()+delay+timeout>=deadline:raise BudgetDeferred('PUBLIC_RECOVERY_DEFERRED')
            if delay:sleep(delay)
            if not store.claim(key,delay=30):raise BudgetDeferred('PUBLIC_RECOVERY_IN_PROGRESS')
        try:
            response=opener(request,timeout=min(timeout,max(.1,deadline-clock())))
            try:
                body=response.read(16*1024*1024+1)
                if len(body)>16*1024*1024:raise ValueError('PUBLIC_RESPONSE_TOO_LARGE')
                buffered=io.BytesIO(body);buffered.headers=response.headers;buffered.status=getattr(response,'status',200)
            finally:response.close()
        except BudgetDeferred as exc:
            if str(exc) not in ('WAIT_API_REQUEST_WEIGHT_BUDGET','WAIT_API_ORDERS_BUDGET','WAIT_API_WEIGHT_BUDGET','WAIT_API_BURST_BUDGET','WEEX_SHARED_COOLDOWN','WEEX_RATE_LIMITS_UNAVAILABLE','WEEX_RATE_LIMIT_REFRESH_IN_PROGRESS'):raise
            ready=budget_ready_at(root,WEIGHTS[parsed.path],clock())
            store.observe('public:budget','API_BUDGET',next_at=ready,evidence_at=clock())
            # Bounded waits, no polling the exchange and no bypassing its budget.
            delay=max(.1,ready-clock())
            if attempt>=3 or delay>30 or clock()+delay+timeout>=deadline:raise
            sleep(delay);attempt+=1;continue
        except Exception as exc:
            if not transient(exc):raise
            store.observe(key,'CONNECTION',next_at=clock()+min(30,2**(attempt+1)),evidence_at=clock())
            attempt+=1
            if attempt>=3:raise
            continue
        # A successful HTTP response verifies connectivity, not candle contents.
        store.resolve(key,clock(),healthy=True)
        store.resolve('public:budget',clock(),healthy=True)
        return buffered
