"""Neutral WEEX execution card for break-even and unknown fills.
No trading operations or Telegram transport.
"""
from io import BytesIO
from PIL import Image,ImageDraw,ImageFont
def render_neutral_fill(trade,action,side):
    im=Image.new('RGB',(1280,720),'#071422')
    d=ImageDraw.Draw(im)
    bold=ImageFont.truetype('C:/Windows/Fonts/arialbd.ttf',46)
    normal=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',31)
    small=ImageFont.truetype('C:/Windows/Fonts/arialbd.ttf',27)
    d.rounded_rectangle((35,32,1245,684),radius=30,fill='#10253b',outline='#2a5476',width=3)
    d.text((80,70),'WEEX  /  FUTURES EXECUTION',font=small,fill='#49cafa')
    label='CHIUSURA IN PAREGGIO' if action=='close' else 'ESECUZIONE DA VERIFICARE'
    d.text((80,165),label,font=bold,fill='#f4f8ff')
    lines=[
        ('COPPIA',str(trade.get('symbol','N/D'))),
        ('DIREZIONE',str(side)),
        ('PREZZO',str(trade.get('price','N/D'))+' USDT'),
        ('QUANTITA',str(trade.get('qty','N/D'))),
        ('PNL REALIZZATO',str(trade.get('realizedPnl','N/D'))+' USDT')]
    for i,(k,v) in enumerate(lines):
        y=265+i*67
        d.text((80,y),k,font=small,fill='#91a8bf')
        d.text((470,y),v[:40],font=normal,fill='#e7f5ff')
    d.text((80,623),'Singola esecuzione · non il PnL netto del ciclo',font=small,fill='#e5b36a')
    b=BytesIO();im.save(b,format='PNG');return b.getvalue()
