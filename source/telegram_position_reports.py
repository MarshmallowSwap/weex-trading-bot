"""Authorized on-demand graphics, on a separate thread so /live_stop stays responsive."""
import json,logging,threading,time,urllib.request,uuid
from pathlib import Path
from weex_position_reports import report
from weex_position_cards import render

COMMANDS=[{'command':'posizioni','description':'Immagine: aperte, leva, TP e PnL non realizzato'},
          {'command':'chiuse24h','description':'Immagine: chiuse nelle ultime 24h e PnL realizzato'}]
CHOICES={'/posizioni':'open','/chiuse24h':'closed','positionreport:open':'open','positionreport:closed':'closed'}
_lock=threading.Lock();_last={}

def selection(update,cfg):
    cb=update.get('callback_query');m=(cb or {}).get('message',{}) if cb else update.get('message',{})
    sender=(cb or m).get('from') or {}
    text=str(cb.get('data','')) if cb else str(m.get('text','')).strip().split(' ')[0].split('@')[0].lower()
    if text not in CHOICES:return None
    authorized=(str(m.get('chat',{}).get('id'))==str(cfg['telegram_chat_id'])
                and str(sender.get('id'))==str(cfg.get('telegram_user_id') or cfg['telegram_chat_id'])
                and not sender.get('is_bot'))
    return CHOICES[text] if authorized else 'unauthorized'

def _send_image(cfg,data,caption):
    boundary='WEEXReport'+uuid.uuid4().hex
    keyboard={'inline_keyboard':[[{'text':'Posizioni aperte','callback_data':'positionreport:open'},
                                 {'text':'Chiuse 24h','callback_data':'positionreport:closed'}]]}
    keyboard['inline_keyboard'].append([{'text':'Posizioni e risultati','callback_data':'aimenu:monitor'},
                                       {'text':'Menu principale','callback_data':'aimenu:home'}])
    fields={'chat_id':str(cfg['telegram_chat_id']),'caption':caption,'reply_markup':json.dumps(keyboard)}
    body=b''
    for k,v in fields.items():body+=(f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n').encode()
    body+=(f'--{boundary}\r\nContent-Disposition: form-data; name="photo"; filename="weex_positions.png"\r\nContent-Type: image/png\r\n\r\n').encode()+data+f'\r\n--{boundary}--\r\n'.encode()
    req=urllib.request.Request('https://api.telegram.org/bot'+cfg['telegram_bot_token']+'/sendPhoto',body,
                               {'Content-Type':'multipart/form-data; boundary='+boundary})
    try:
        with urllib.request.urlopen(req,timeout=20) as response:value=json.load(response)
        if value.get('ok') is not True:raise ValueError('SEND_FAILED')
        return value['result']['message_id']
    except Exception:raise RuntimeError('REPORT_IMAGE_DELIVERY_UNCERTAIN') from None

def send_image(cfg,data,caption):
    from weex_alert_archive import observed,image_content
    root=Path(__file__).resolve().parent
    return observed(root,'commands.position_report','sendPhoto',image_content(data,caption,root=root),lambda:_send_image(cfg,data,caption))

def deliver(kind,cfg,root,*,get_report=report,renderer=render,sender=send_image):
    data=get_report(kind,root);images=renderer(data);ids=[]
    caption=('Posizioni aperte: PnL non realizzato.' if kind=='open' else
             'Chiusure ultime 24h: PnL lordo e netto commissioni (funding escluso). Leva e TP storici, se verificati.')
    if data['stale']:caption='DATI NON AGGIORNATI. '+str(data.get('error'))+'. '+caption
    for index,image in enumerate(images):ids.append(sender(cfg,image,f'{caption} Pagina {index+1}/{len(images)}.'))
    return ids

def handle(update,cfg,root):
    kind=selection(update,cfg)
    if kind is None:return False
    if kind=='unauthorized':return True
    # Bound background work and avoid unlimited queues from repeated taps.
    if not _lock.acquire(blocking=False):return {'notice':'Un riepilogo è già in preparazione. Riprova tra pochi secondi.'}
    if time.monotonic()-_last.get(kind,-1e9)<10:
        _lock.release();return {'notice':'Riepilogo appena richiesto. Attendi qualche secondo prima di aggiornarlo.'}
    _last[kind]=time.monotonic()
    def job():
        try:deliver(kind,dict(cfg),Path(root))
        except Exception as exc:logging.warning('Position graphic delivery failed (%s); no blind retry',type(exc).__name__)
        finally:_lock.release()
    threading.Thread(target=job,name='weex-position-report',daemon=True).start()
    return True
