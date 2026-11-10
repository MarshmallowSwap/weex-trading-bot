"""Explicit demo allowlist; never infer demo contracts by suffix alone."""
from urllib.parse import urlparse
BASE="https://api-contract.weex.com"
DEMO_SYMBOLS=frozenset(("BTCSUSDT",)) # documented example; not exchange-order validated
READ=frozenset(("/capi/v3/sim/balance","/capi/v3/sim/position/allPosition"))
WRITE=frozenset(("/capi/v3/sim/order",))
def authorize(method,url,symbol=None,allow_demo_writes=False):
 u=urlparse(url)
 if u.scheme!="https" or u.netloc!="api-contract.weex.com" or u.query or u.fragment:
  return {"allowed":False,"reason":"UNTRUSTED_TARGET"}
 if not u.path.startswith("/capi/v3/sim/"):return {"allowed":False,"reason":"NOT_DEMO_ENDPOINT"}
 if symbol is not None and symbol not in DEMO_SYMBOLS:return {"allowed":False,"reason":"NOT_VERIFIED_DEMO_SYMBOL"}
 if method=="GET" and u.path in READ:return {"allowed":True,"reason":"DEMO_READ"}
 if method=="POST" and u.path in WRITE and allow_demo_writes and symbol in DEMO_SYMBOLS:
  return {"allowed":True,"reason":"DEMO_WRITE_CONFIG_ONLY"}
 return {"allowed":False,"reason":"DENIED"}
