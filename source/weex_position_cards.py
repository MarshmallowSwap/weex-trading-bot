"""Deterministic data cards; values always come from read-only reports."""
import io, math
from datetime import datetime,timezone
from decimal import Decimal as D
from PIL import Image, ImageDraw, ImageFont

BG='#060d1b';PANEL='#102139';LINE='#26445f';WHITE='#edf5ff';MUTED='#9bb0c8'
CYAN='#31d7f3';GREEN='#2ee5a2';RED='#ff6482';AMBER='#ffbd5b'

def font(size,bold=False):
    return ImageFont.truetype('C:/Windows/Fonts/'+('seguisb.ttf' if bold else 'segoeui.ttf'),size)

def fmt(value,signed=False,places=4):
    if value is None:return 'N/D'
    n=D(str(value))
    return format(n,('+' if signed else '')+f',.{places}f')

def price(value):
    if value is None:return 'N/D'
    return format(D(str(value)),'.8f').rstrip('0').rstrip('.')

def local(ms):
    return datetime.fromtimestamp(ms/1000,timezone.utc).astimezone().strftime('%d/%m %H:%M:%S') if ms else 'non disponibile'

def render(report):
    rows=report['rows'];kind=report['kind'];pages=max(1,math.ceil(len(rows)/3));images=[]
    complete=all(r.get('pnl') is not None for r in rows)
    total=sum((D(r['pnl']) for r in rows if r.get('pnl') is not None),D(0)) if complete and report['observedAtMs'] else None
    for page in range(pages):
        chunk=rows[page*3:page*3+3];h=510+max(1,len(chunk))*260
        im=Image.new('RGB',(1080,h),BG);d=ImageDraw.Draw(im)
        def text(x,y,value,size=24,color=WHITE,bold=False,width=None):
            s=str(value);f=font(size,bold)
            while width and d.textlength(s,font=f)>width and size>16:size-=1;f=font(size,bold)
            if width and d.textlength(s,font=f)>width:
                while s and d.textlength(s+'...',font=f)>width:s=s[:-1]
                s+='...'
            d.text((x,y),s,font=f,fill=color)
        d.rounded_rectangle((30,30,1050,205),radius=24,fill=PANEL,outline=CYAN,width=2)
        text(58,48,'WEEX  /  AI DESK',40,CYAN,True)
        text(58,105,'POSIZIONI APERTE' if kind=='open' else 'POSIZIONI CHIUSE · 24 ORE',32,WHITE,True)
        text(58,157,'Dati: '+local(report['observedAtMs'])+' · ora locale PC',21,MUTED)
        text(935,61,f'{page+1}/{pages}',24,MUTED)
        status=report.get('error') or ('Ultime 24h fino alle '+local(report['windowEndMs']) if kind=='closed' else 'Conto reale · USDT · sola lettura')
        if report['stale']:status='DATI NON AGGIORNATI · '+status
        text(40,222,status,24,AMBER if report['stale'] else MUTED,width=1000)
        text(40,263,f'{len(rows)} posizioni' if report['observedAtMs'] else 'Posizioni: non disponibili',26,WHITE,True)
        text(450,260,('PnL non realizzato' if kind=='open' else 'Realizzato lordo 24h')+'  '+fmt(total,True)+' USDT',27,
             GREEN if total is not None and total>=0 else RED if total is not None else MUTED,True,width=590)
        if not chunk:
            d.rounded_rectangle((30,322,1050,548),radius=20,fill=PANEL,outline=LINE,width=2)
            text(65,393,'Nessuna posizione '+('aperta' if kind=='open' else 'chiusa nel periodo') if report['observedAtMs'] else 'Dati non disponibili: riprova tra poco',30,WHITE,True,width=950)
        for index,r in enumerate(chunk):
            y=322+index*260;color=GREEN if r['side']=='LONG' else RED
            d.rounded_rectangle((30,y,1050,y+242),radius=20,fill=PANEL,outline=LINE,width=2)
            d.rounded_rectangle((30,y+20,36,y+222),radius=3,fill=color)
            text(56,y+18,r['symbol'],32,WHITE,True,width=330)
            text(390,y+22,r['side'],26,color,True)
            text(535,y+22,(price(r.get('leverage'))+'x') if r.get('leverage') else 'Leva N/D',26,CYAN,True)
            pn=D(r['pnl']) if r.get('pnl') is not None else None
            text(725,y+16,fmt(pn,True)+' USDT',29,GREEN if pn is not None and pn>=0 else RED if pn is not None else MUTED,True,width=300)
            text(726,y+57,'NON REALIZZATO' if kind=='open' else 'REALIZZATO LORDO',17,MUTED)
            text(56,y+71,'Entry '+price(r.get('entry'))+'  |  Q.tà '+price(r['quantity']),23,MUTED,width=650)
            tps=r.get('tp') or ['N/D']
            text(56,y+112,'TP  '+tps[0],25,AMBER if 'ASSENTE' in tps[0] or 'N/D' in tps[0] else WHITE,width=950)
            if len(tps)>1:text(56,y+146,'Altri TP: '+'; '.join(tps[1:]),19,MUTED,width=950)
            if kind=='closed':
                text(56,y+174,'Exit '+price(r.get('exit'))+'  |  '+local(r['closedAt']),20,MUTED,width=620)
                text(700,y+157,'NETTO* '+fmt(r.get('net'),True),26,CYAN,True,width=320)
                text(700,y+192,'Fee '+fmt(r.get('fees'))+' USDT',19,MUTED,width=320)
                if not r.get('fullCycle'):text(56,y+207,'Apertura precedente al periodo: dati parziali del ciclo',17,AMBER,width=620)
            else:
                if r.get('tpGrossTargetUSDT') is not None and r.get('tpNetEstimatedUSDT') is not None:
                    text(56,y+150,'TP lordo obiettivo  '+fmt(r['tpGrossTargetUSDT'],True,2)+' USDT',20,CYAN,width=950)
                    text(56,y+184,'Netto stimato al trigger  '+fmt(r['tpNetEstimatedUSDT'],True,2)+' USDT*',21,GREEN,True,width=950)
                    text(56,y+216,'* Fee stimate; esecuzione e funding esclusi',15,MUTED,width=950)
                else:
                    text(56,y+190,'PnL WEEX · commissioni e funding non sottratti',20,MUTED,width=950)
        footer=322+max(1,len(chunk))*260+16
        notes=(['Leva storica: valore verificato all’ingresso, ove disponibile.',
                '* Netto: commissioni di apertura + chiusura sottratte; funding escluso.',
                'Riduzioni di posizioni ancora aperte: '+fmt(report.get('partialRealized'),True)+' USDT lordi (escluse sopra).']
               if kind=='closed' else ['TP: prezzo trigger effettivo e copertura osservata su WEEX.',
                                       'Aggiornamento su richiesta; eventuale cache dura 30 secondi.'])
        for i,note in enumerate(notes):text(40,footer+31*i,note,19,MUTED,width=1000)
        b=io.BytesIO();im.save(b,format='PNG');images.append(b.getvalue())
    return images
