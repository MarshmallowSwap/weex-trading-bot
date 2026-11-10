"""One-shot authorized QNT-only reconciliation using the existing WEEX workflow.

This stops new live entries. It cannot automatically re-arm. No new entries.
"""
import json
from monitor import ROOT,TG
from weex_reconcile import run
cfg=json.loads(TG.read_text(encoding='utf-8'))
chat=str(cfg['telegram_chat_id'])
user=str(cfg.get('telegram_user_id') or chat)
result=run(ROOT,user,chat,symbol='QNTUSDT')
print(json.dumps(result,indent=2))
