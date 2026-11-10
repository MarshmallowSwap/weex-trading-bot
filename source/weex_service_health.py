"""Heartbeat only after the relevant service loop completes successfully."""
import json,os,time
from datetime import datetime,timezone
from pathlib import Path

def publish(root,service):
    if service not in ('telegram','notifications'):raise ValueError('UNKNOWN_SERVICE')
    target=Path(root)/('weex_service_health_'+service+'.json')
    # Separate files per service; concurrent duplicate process writes cannot
    # overwrite another PID's temporary file. Inventory still rejects duplicates.
    tmp=target.with_suffix('.'+str(os.getpid())+'.tmp')
    result={'checkedAt':datetime.now(timezone.utc).isoformat(),'pid':os.getpid(),'status':'OK'}
    tmp.write_text(json.dumps(result),encoding='utf-8');tmp.replace(target)

def tick(root,sender):
    from weex_incidents import Store
    store=Store(root)
    store.drain(sender)
    # Local notification loop health, NOT proof of Telegram delivery or fills.
    publish(root,'notifications')
