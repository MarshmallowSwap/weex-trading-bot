"""One durable graphical Telegram message per order/position-side/action.

Aggregates observed fills only; does not claim the exchange order is complete.
No WEEX calls. No trading state writes. Late fills edit the acknowledged photo.
"""
import hashlib,json,sqlite3,time,uuid,urllib.request,logging,sys
from decimal import Decimal
from contextlib import closing
from pathlib import Path
from html import escape

def number(v):
    n=Decimal(str(v))
    if not n.is_finite():raise ValueError('NONFINITE_FILL')
    return n

def identity(f):
    if not all(f.get(k) is not None and str(f[k]) for k in ('symbol','orderId','positionSide','side','id')):raise ValueError('MISSING_FILL_IDENTITY')
    if f['positionSide'] not in ('LONG','SHORT') or f['side'] not in ('BUY','SELL'):raise ValueError('UNKNOWN_DIRECTION')
    return json.dumps([str(f[k]) for k in ('symbol','positionSide','side','orderId')],separators=(',',':'))

def summarize(fills):
    unique={};key=None
    for f in fills:
        k=identity(f)
        if key is not None and key!=k:raise ValueError('MIXED_ORDERS')
        key=k;fid=str(f['id'])
        if fid in unique and unique[fid]!=f:raise ValueError('CONFLICTING_FILL')
        unique[fid]=f
    if not unique:raise ValueError('EMPTY_ORDER')
    qty=Decimal(0);value=Decimal(0);pnl=Decimal(0);fees={};times=[]
    for f in unique.values():
        q=number(f['qty']);v=number(f['quoteQty']);price=number(f['price'])
        if min(q,v,price)<=0:raise ValueError('INVALID_FILL_AMOUNT')
        qty+=q;value+=v;pnl+=number(f['realizedPnl'])
        asset=str(f['commissionAsset']);fees[asset]=fees.get(asset,Decimal(0))+number(f['commission'])
        times.append(int(f['time']))
    symbol,position,side,order=json.loads(key)
    return {'key':key,'symbol':symbol,'positionSide':position,'side':side,'orderId':order,
        'action':'OPEN' if (position,side) in [('LONG','BUY'),('SHORT','SELL')] else 'CLOSE',
        'quantity':str(qty),'quoteQty':str(value),'averagePrice':str(value/qty),'realizedPnl':str(pnl),
        'fees':{a:str(v) for a,v in sorted(fees.items())},'fillCount':len(unique),'firstTime':min(times),'lastTime':max(times),
        'fillIds':sorted(unique),'completeOrderVerified':False}

def schema(c):
    c.executescript('''CREATE TABLE IF NOT EXISTS events(id TEXT PRIMARY KEY,status TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS fill_alert_fills_v1(order_key TEXT,fill_id TEXT,payload TEXT,PRIMARY KEY(order_key,fill_id));
    CREATE TABLE IF NOT EXISTS fill_alert_orders_v1(order_key TEXT PRIMARY KEY,revision INTEGER,sent_revision INTEGER,
      message_id INTEGER,state TEXT,summary TEXT,updated REAL);
    CREATE TABLE IF NOT EXISTS fill_alert_extras_v1(message_id INTEGER PRIMARY KEY,order_key TEXT,min_revision INTEGER,
      sent_at REAL,state TEXT,evidence TEXT);
    CREATE TABLE IF NOT EXISTS fill_alert_meta_v1(key TEXT PRIMARY KEY,value TEXT);''')

def scope(c,cfg):
    value=hashlib.sha256(json.dumps([cfg['telegram_bot_token'],str(cfg['telegram_chat_id'])]).encode()).hexdigest()
    row=c.execute("SELECT value FROM fill_alert_meta_v1 WHERE key='destination'").fetchone()
    if row and row[0]!=value:raise ValueError('DESTINATION_CHANGED')
    c.execute("INSERT OR IGNORE INTO fill_alert_meta_v1 VALUES('destination',?)",(value,))

def ingest(c,fills,now=None):
    now=time.time() if now is None else now;schema(c);changed=set()
    with c:
        c.execute('BEGIN IMMEDIATE')
        for f in fills:
            fid=str(f['id'])
            if c.execute('SELECT 1 FROM events WHERE id=?',(fid,)).fetchone():continue
            key=identity(f);summarize([f])
            c.execute('INSERT INTO fill_alert_fills_v1 VALUES(?,?,?)',(key,fid,json.dumps(f,sort_keys=True)))
            c.execute("INSERT INTO events VALUES(?,'aggregated')",(fid,));changed.add(key)
        for key in changed:
            allfills=[json.loads(r[0]) for r in c.execute('SELECT payload FROM fill_alert_fills_v1 WHERE order_key=?',(key,))]
            summary=json.dumps(summarize(allfills),sort_keys=True)
            c.execute('''INSERT INTO fill_alert_orders_v1 VALUES(?,1,0,NULL,'READY',?,?)
              ON CONFLICT(order_key) DO UPDATE SET revision=revision+1,summary=excluded.summary,updated=excluded.updated''',(key,summary,now))
    return len(changed)

def seed(c,receipts,cfg,now=None):
    """Import exact archived photo receipts for the explicitly identified repair."""
    now=time.time() if now is None else now
    if len(receipts)<2:raise ValueError('NO_MULTIFILL_REPAIR')
    if any(r['method']!='sendPhoto' or not 0<=now-r['at']<47*3600 or not isinstance(r['messageId'],int) for r in receipts):raise ValueError('UNSAFE_RECEIPT')
    summary=summarize([r['fill'] for r in receipts]);key=summary['key']
    ids=[r['messageId'] for r in receipts]
    if len(ids)!=len(set(ids)):raise ValueError('REPEATED_MESSAGE_ID')
    schema(c)
    with c:
        c.execute('BEGIN IMMEDIATE');scope(c,cfg)
        if c.execute('SELECT 1 FROM fill_alert_orders_v1 WHERE order_key=?',(key,)).fetchone():return False
        for r in receipts:
            f=r['fill'];fid=str(f['id'])
            c.execute('INSERT OR IGNORE INTO fill_alert_fills_v1 VALUES(?,?,?)',(key,fid,json.dumps(f,sort_keys=True)))
            c.execute("INSERT OR IGNORE INTO events VALUES(?,'aggregated')",(fid,))
        c.execute("INSERT INTO fill_alert_orders_v1 VALUES(?,1,0,?,'READY',?,?)",(key,ids[0],json.dumps(summary,sort_keys=True),now))
        for r in receipts[1:]:
            c.execute("INSERT INTO fill_alert_extras_v1 VALUES(?,?,1,?,'PENDING',?)",(r['messageId'],key,r['at'],json.dumps(r,sort_keys=True)))
    return True

def display(s):
    def fmt(v):return format(number(v).quantize(Decimal('.00000001')),'f').rstrip('0').rstrip('.') or '0'
    price=fmt(s['averagePrice']);pnl=number(s['realizedPnl'])
    kind=('long' if s['positionSide']=='LONG' else 'short') if s['action']=='OPEN' else ('profit' if pnl>0 else 'loss' if pnl<0 else 'neutral')
    fields=([('COIN',s['symbol']),('ENTRY',price),('SIZE',s['quantity']),('LEVA','N/D'),('ORA',time.strftime('%H:%M UTC',time.gmtime(s['lastTime']/1000)))]
        if s['action']=='OPEN' else [('COIN',s['symbol']),('PNL',fmt(pnl)+' USDT'),('ROI','N/D'),('EXIT',price),('DURATA','N/D')])
    caption=f"<b>WEEX | {s['action']} {escape(s['positionSide'])} — {escape(s['symbol'])}</b>\n"
    caption+=f"Quantità eseguita: <b>{escape(s['quantity'])}</b>\nPrezzo medio: <b>{price} USDT</b>\n"
    caption+='Commissioni di questo ordine: '+', '.join(fmt(v)+' '+escape(a) for a,v in s['fees'].items())+'\n'
    if s['action']=='CLOSE':caption+='PnL realizzato lordo: '+fmt(pnl)+' USDT (commissioni separate)\n'
    caption+=f"Fill osservati: {s['fillCount']}\nOrdine: {escape(s['orderId'])}\nRiepilogo aggiornato con le esecuzioni disponibili."
    return kind,fields,caption

def transport(root,cfg,summary,message_id=None):
    # Same local graphical renderer; the shared Hyperliquid sender is unchanged.
    sys.path.insert(0,r'D:\FUNDSHOT\hyperliquid_alerts')
    from cards import render
    from weex_alert_archive import observed,image_content
    kind,fields,caption=display(summary)
    if kind=='neutral':
        from weex_neutral_fill_card import render_neutral_fill
        data=render_neutral_fill({'symbol':summary['symbol'],
             'price':summary['averagePrice'],'qty':summary['quantity'],
             'realizedPnl':summary['realizedPnl']},'close',summary['positionSide'])
        media_type='image/png';filename='summary.png'
    else:
        data=render(kind,fields);media_type='image/jpeg';filename='summary.jpg'
    boundary='----WEEXAggregate'+uuid.uuid4().hex
    def part(name,value,filename=None):
        header=f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"'
        if filename:header+=f'; filename="{filename}"\r\nContent-Type: {media_type}'
        return (header+'\r\n\r\n').encode()+(value if isinstance(value,bytes) else str(value).encode())+b'\r\n'
    body=part('chat_id',cfg['telegram_chat_id'])
    if message_id is None:
        method='sendPhoto';body+=part('caption',caption)+part('parse_mode','HTML')+part('photo',data,filename)
    else:
        method='editMessageMedia';body+=part('message_id',message_id)
        body+=part('media',json.dumps({'type':'photo','media':'attach://photo','caption':caption,'parse_mode':'HTML'}))+part('photo',data,filename)
    body+=f'--{boundary}--\r\n'.encode()
    content=image_content(data,caption,fields=summary)  # summary retains all fill IDs
    def dispatch():
        request=urllib.request.Request('https://api.telegram.org/bot'+cfg['telegram_bot_token']+'/'+method,body,{'Content-Type':'multipart/form-data; boundary='+boundary})
        with urllib.request.urlopen(request,timeout=20) as response:result=json.load(response)
        if result.get('ok') is not True or not isinstance(result.get('result'),dict):raise RuntimeError('TELEGRAM_ACK_MISSING')
        ack=result['result'].get('message_id')
        if type(ack) is not int or (message_id is not None and ack!=message_id):raise RuntimeError('TELEGRAM_ID_MISMATCH')
        return result
    result=observed(root,'monitor.order',method,content,dispatch)
    return result['result']['message_id']

def drain(c,root,cfg,sender=None,deleter=None,now=None):
    now=time.time() if now is None else now;schema(c)
    with c:scope(c,cfg)
    rows=c.execute("SELECT order_key,revision,message_id,summary FROM fill_alert_orders_v1 WHERE state='READY' AND revision>sent_revision ORDER BY updated LIMIT 5").fetchall()
    results=[]
    for key,rev,mid,payload in rows:
        with c:
            claimed=c.execute("UPDATE fill_alert_orders_v1 SET state='SENDING' WHERE order_key=? AND state='READY' AND revision=?",(key,rev)).rowcount
        if not claimed:continue
        try:
            ack=(sender or transport)(root,cfg,json.loads(payload),mid)
            if type(ack) is not int or ack<=0 or (mid is not None and ack!=mid):raise ValueError('ACK_INVALID')
            with c:c.execute("UPDATE fill_alert_orders_v1 SET state='READY',message_id=?,sent_revision=? WHERE order_key=?",(ack,rev,key))
            results.append({'orderKey':key,'messageId':ack,'status':'EDITED' if mid else 'SENT'})
        except Exception as exc:
            with c:c.execute("UPDATE fill_alert_orders_v1 SET state='DELIVERY_UNCERTAIN' WHERE order_key=?",(key,))
            logging.warning('Order alert uncertain (%s); no blind resend',type(exc).__name__)
            results.append({'orderKey':key,'status':'DELIVERY_UNCERTAIN'})
    # Remove old tranche photos only after confirmed edit covering every fill.
    extras=c.execute('''SELECT e.message_id,e.order_key,e.sent_at FROM fill_alert_extras_v1 e
      JOIN fill_alert_orders_v1 o ON o.order_key=e.order_key WHERE e.state='PENDING'
      AND o.sent_revision>=e.min_revision AND o.message_id!=e.message_id AND o.state='READY' LIMIT 5''').fetchall()
    if deleter is None:
        from weex_telegram_cleanup import delete_message
        deleter=delete_message
    for mid,key,sent in extras:
        with c:
            claimed=c.execute("UPDATE fill_alert_extras_v1 SET state=? WHERE message_id=? AND state='PENDING'",('DELETING' if 0<=now-sent<47*3600 else 'EXPIRED',mid)).rowcount
        if not claimed or not 0<=now-sent<47*3600:continue
        try:
            if deleter(cfg,mid) is not True:raise ValueError('DELETE_UNCONFIRMED')
            status='DELETED'
        except Exception as exc:
            status='DELETE_UNCERTAIN';logging.warning('Tranche cleanup uncertain (%s)',type(exc).__name__)
        with c:c.execute('UPDATE fill_alert_extras_v1 SET state=? WHERE message_id=?',(status,mid))
        results.append({'messageId':mid,'status':status})
    return results
