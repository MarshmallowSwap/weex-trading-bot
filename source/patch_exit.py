from pathlib import Path
p=Path(__file__).parent/"monitor.py"
s=p.read_text(encoding="utf-8")
assert s.count('def send(t,cfg):')==1
s=s.replace('def send(t,cfg):', '''def exit_type_for_trade(t):
 # WEEX order history is authoritative when the executed order ID matches.
 oid=str(t.get("orderId",""))
 if not oid:return "NON VERIFICATO"
 try:
  result=query("/capi/v3/order/history?limit=100&page=0")
  matches=[x for x in result if str(x.get("orderId",""))==oid]
  if not matches:return "NON VERIFICATO"
  order=matches[0]
  kind=str(order.get("type","")).upper()
  if "TAKE_PROFIT" in kind or kind.startswith("TP"):return "TP"
  if "STOP" in kind or "STOP_LOSS" in kind:return "SL (BREAKEVEN N/D)"
  if kind in ("LIMIT","MARKET"):return "ORDINE "+kind
  return "NON VERIFICATO"
 except Exception:
  logging.exception("WEEX exit type lookup failed")
  return "NON VERIFICATO"

def send(t,cfg):''')
old='''  send_photo(cfg,kind,fields,info+("\\nEXIT TYPE: non ancora verificato su WEEX" if action=="close" else ""))'''
new='''  exit_type=exit_type_for_trade(t) if action=="close" else None
  send_photo(cfg,kind,fields,info+("\\nEXIT TYPE: "+exit_type if exit_type else ""),exit_type=exit_type)'''
assert s.count(old)==1
s=s.replace(old,new)
p.write_text(s,encoding="utf-8")
print("WEEX_EXIT_TYPE_PATCH_OK")
