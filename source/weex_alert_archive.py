"""Best-effort outbound audit trail; never retries or changes Telegram delivery.

No Telegram/WEEX transport here. Only explicitly provided message content and
safe metadata are retained. Credentials, request URLs and headers are excluded.
"""
import json,logging,re,sqlite3,time,uuid
from contextlib import closing
from pathlib import Path

NAME='weex_alert_archive.sqlite3'
FIELDS={'symbol','id','orderId','time','qty','price','quoteQty','commission','commissionAsset','realizedPnl','side','positionSide'}
SCHEMA='''CREATE TABLE IF NOT EXISTS outbound_events_v1(
                seq INTEGER PRIMARY KEY AUTOINCREMENT,attempt_id TEXT NOT NULL,at REAL NOT NULL,
                stage TEXT NOT NULL,source TEXT NOT NULL,method TEXT NOT NULL,content TEXT NOT NULL,outcome TEXT NOT NULL)'''

def initialize(root):
    with closing(sqlite3.connect(Path(root)/NAME,timeout=.1)) as c,c:c.execute(SCHEMA)

def clean(value):
    if isinstance(value,str):
        value=re.sub(r'(?i)(?:bot)?\d{6,}:[A-Za-z0-9_-]{20,}','[TOKEN REDACTED]',value)
        value=re.sub(r'(?i)((?:api[_-]?key|secret[_-]?key|passphrase|access-sign)\s*[:=]\s*)[^\s,;]+',r'\1[REDACTED]',value)
        return value
    if isinstance(value,dict):
        return {str(k):clean(v) for k,v in value.items() if not any(x in str(k).lower() for x in ('token','secret','passphrase','api_key','header','request_url'))}
    if isinstance(value,(list,tuple)):return [clean(v) for v in value]
    if value is None or isinstance(value,(int,float,bool)):return value
    return str(value)

def append(root,ident,stage,source,method,content,result=None,error=None):
    try:
        safe=clean(content);response=(result or {}).get('result',result) if isinstance(result,dict) else {}
        response=response if isinstance(response,dict) else {}
        if type(result) is int:response={'message_id':result}
        outcome={'messageId':response.get('message_id'),'telegramDate':response.get('date'),'errorClass':error}
        with closing(sqlite3.connect(Path(root)/NAME,timeout=.1)) as c,c:
            c.execute(SCHEMA)
            c.execute('INSERT INTO outbound_events_v1(attempt_id,at,stage,source,method,content,outcome) VALUES(?,?,?,?,?,?,?)',
                      (ident,time.time(),stage,source,method,json.dumps(safe,ensure_ascii=False),json.dumps(outcome)))
    except Exception as exc:
        # Losing an audit record must never resend or suppress the real alert.
        logging.warning('Outbound audit unavailable (%s)',type(exc).__name__)

def observed(root,source,method,content,send):
    ident=uuid.uuid4().hex
    append(root,ident,'SENDING',source,method,content)
    try:result=send()
    except BaseException as exc:
        append(root,ident,'DELIVERY_UNCERTAIN',source,method,content,error=type(exc).__name__)
        raise
    append(root,ident,'SENT',source,method,content,result=result)
    return result

def photo_sender(original,root,source,trade=None):
    def send(cfg,kind,items,caption,exit_type=None):
        content={'kind':kind,'items':items,'caption':caption[:1000],'exitType':exit_type}
        if trade is not None:content['fill']={k:v for k,v in trade.items() if k in FIELDS}
        return observed(root,source,'sendPhoto',content,lambda:original(cfg,kind,items,caption,exit_type=exit_type))
    return send

def image_content(data,caption=None,fields=None,root=None):
    # The hash identifies the actual PNG; numerical fields are separately saved
    # so analysis need not infer financial values from pixels.
    import hashlib
    digest=hashlib.sha256(data).hexdigest()
    content={'caption':caption,'imageSha256':digest,'imageBytes':len(data),'fields':fields}
    if root is not None:
        try:
            folder=Path(root)/'weex_alert_images';folder.mkdir(exist_ok=True)
            path=folder/(digest+'.png')
            if not path.exists():path.write_bytes(data)
            content['imageFile']=str(path)
        except Exception as exc:content['imageArchiveError']=type(exc).__name__
    return content

def file_photo_sender(original,root,source,filename,label):
    def send(*args,**kwargs):
        content={'kind':label}
        def dispatch():
            result=original(*args,**kwargs)
            try:content.update(image_content((Path(root)/filename).read_bytes(),root=root))
            except Exception as exc:content['imageArchiveError']=type(exc).__name__
            return result
        return observed(root,source,'sendPhoto',content,dispatch)
    return send
