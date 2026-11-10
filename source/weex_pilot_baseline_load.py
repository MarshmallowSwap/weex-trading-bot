"""Validate saved flat pilot baseline before relying on ownership attestation.

Digest detects accidental edits; it does NOT authenticate exchange provenance.
Authenticated origin is provided only by the capture process.
"""
import hashlib,json,time
from pathlib import Path
def load(path,*,now_ms=None,max_age_ms=600000):
 try:
  raw=json.loads(Path(path).read_text(encoding='utf-8'))
  digest=raw.pop('snapshotSha256')
  actual=hashlib.sha256(json.dumps(raw,sort_keys=True,separators=(',',':')).encode()).hexdigest()
  stamp=int(raw['observedAtMs']);now=int(time.time()*1000) if now_ms is None else now_ms
  if digest!=actual or not 0<=now-stamp<=max_age_ms:
   return None
  if (raw.get('snapshotVerified') is not True or raw.get('account')!='CURRENT_WEEX'
      or raw.get('productionMode')!='STOPPED'
      or not all(isinstance(raw.get(k),list) and not raw[k]
          for k in ('positions','regularOrders','conditionalOrders'))):
   return None
  return raw
 except (OSError,ValueError,KeyError,TypeError,AttributeError):
  return None
