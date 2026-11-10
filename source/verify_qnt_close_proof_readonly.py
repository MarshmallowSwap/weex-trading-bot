"""READ ONLY historical proof for QNT; no account-state changes or orders."""
import json
from pathlib import Path
from weex_live_worker import Reader
from weex_reconcile import Reconciler
import live_control
root=Path(__file__).resolve().parent
r=Reconciler(root,Reader(root),live_control.state(root),lambda *a,**k:None,timeout=45)
item=r.engine.get('wxentry_7f327b721a398e3e86033c73')
proof=r.gather(item)['proof']
print(json.dumps({'resolution':proof.get('resolution'),'botTPUsed':proof.get('botTPUsed'),
                   'quantity':proof.get('quantity'),'exitOrderIds':proof.get('exitOrderIds'),
                   'realizedNetBeforeFundingUSDT':proof.get('realizedNetBeforeFundingUSDT'),
                   'evidenceSha256':proof.get('evidenceSha256')},indent=2))
