"""One-time Telegram-only TEST image. Never touches WEEX or enables trading."""
import copy,io,json,tempfile
from pathlib import Path
from datetime import datetime,timezone
from PIL import Image,ImageDraw,ImageFont
import live_control
from test_weex_lifecycle import Exchange,CFG,PLAN
from weex_lifecycle import Lifecycle,now
from weex_position_reports import bot_tp_previews,open_rows
from weex_position_cards import render
from telegram_position_reports import send_image
from monitor import ROOT,TG
MARKER=ROOT/'telegram_gross_net_simulation_delivery.json'
if __name__=='__main__':
 if live_control.state(ROOT)['mode']!='STOPPED':raise PermissionError('LIVE_MUST_STAY_STOPPED')
 if live_control.build_errors(ROOT):raise PermissionError('INTEGRITY_FAILED')
 if MARKER.exists():raise PermissionError('NO_RETRY_DELIVERY_ALREADY_ATTEMPTED')
 cfg_tg=json.loads(TG.read_text(encoding='utf-8'))
 if not cfg_tg.get('telegram_bot_token') or not str(cfg_tg.get('telegram_chat_id','')).strip():
  raise PermissionError('INVALID_TELEGRAM_DESTINATION')
 with tempfile.TemporaryDirectory() as dirname:
  root=Path(dirname)
  config=copy.deepcopy(CFG)
  config['strategySettings'].update(targetNetProfitUSDT=20,tpAccountingMode='GROSS_BEFORE_COSTS')
  plan=copy.deepcopy(PLAN)
  plan.update(targetNetProfitUSDT='20',tpAccountingMode='GROSS_BEFORE_COSTS')
  fake=Exchange()
  engine=Lifecycle(root/'weex_user_live_lifecycle.sqlite3',fake,lambda:config)
  item=engine.prepare('telegram-gross-net-visual-check',plan)
  def context(symbol):
   return {'observedAtMs':now(),'complete':True,'apiEnabled':True,
    'accountCanTrade':True,'hedgeMode':True,'depthUnitVerified':True,
    'liquidityPassed':True,'marketSignal':'LONG','riskTierVerified':True,
    'availableBalance':'100','positions':[],'openOrders':[],'conditionalOrders':[],
    'symbolConfig':{'symbol':symbol,'marginType':fake.margin,'crossLeverage':fake.leverage},
    'referencePrice':'2500','exitFeeRate':'.0008','maximumPermittedLeverage':'100'}
  if engine.advance(item['id'],context)['state']!='TP_PENDING':raise RuntimeError('SIM_ENTRY_FAILED')
  if engine.reconcile(item['id'])['state']!='PROTECTED':raise RuntimeError('SIM_TP_FAILED')
  position={**fake.positions[0],'asset':'USDT','leverage':'100',
   'openValue':'50.00','openFee':'0.04','unrealizePnl':'0','marginType':'CROSSED'}
  row=open_rows([position],fake.algos,tp_previews=bot_tp_previews(root))[0]
  if row.get('tpGrossTargetUSDT')!='20' or row.get('tpNetEstimatedUSDT') is None:
   raise RuntimeError('SIM_PREVIEW_MISSING')
  nowms=int(datetime.now(timezone.utc).timestamp()*1000)
  raw=render({'kind':'open','rows':[row],'observedAtMs':nowms,
              'windowEndMs':nowms,'stale':False,'error':None})[0]
  im=Image.open(io.BytesIO(raw)).convert('RGB')
  d=ImageDraw.Draw(im)
  font=ImageFont.truetype('C:/Windows/Fonts/seguisb.ttf',38)
  d.rounded_rectangle((180,220,900,300),radius=14,fill='#8C1E35',outline='#FFB3C0',width=3)
  d.text((255,235),'SIMULAZIONE - NO ORDINI',font=font,fill='#FFFFFF')
  buffer=io.BytesIO();im.save(buffer,format='PNG')
  caption=('TEST GRAFICO WEEX - SIMULAZIONE, NON E UNA POSIZIONE REALE. '
           'TP lordo +20 USDT e netto stimato sulla posizione simulata; '
           'costi stimati e funding escluso. Nessun ordine inviato.')
  # Pre-dispatch attempt marker is intentional: ambiguous Telegram delivery must never retry.
  marker={'state':'ATTEMPT_STARTED','atUTC':datetime.now(timezone.utc).isoformat(),
          'noExchangeWrites':True,'symbolIsSimulated':True}
  MARKER.write_text(json.dumps(marker,indent=2),encoding='utf-8')
  try:
   msg_id=send_image(cfg_tg,buffer.getvalue(),caption)
  except Exception as e:
   marker.update(state='DELIVERY_UNCERTAIN',errorType=type(e).__name__)
   MARKER.write_text(json.dumps(marker,indent=2),encoding='utf-8')
   print(json.dumps({'delivery':'UNCERTAIN_NO_RETRY','errorType':type(e).__name__,
                     'botMode':live_control.state(ROOT)['mode']}))
  else:
   marker.update(state='SENT',telegramMessageId=int(msg_id),
                 grossTargetUSDT=row['tpGrossTargetUSDT'],
                 estimatedNetUSDT=row['tpNetEstimatedUSDT'])
   MARKER.write_text(json.dumps(marker,indent=2),encoding='utf-8')
   print(json.dumps({'delivery':'SENT','telegramMessageId':int(msg_id),
                     'grossTargetUSDT':row['tpGrossTargetUSDT'],
                     'estimatedNetUSDT':row['tpNetEstimatedUSDT'],
                     'botMode':live_control.state(ROOT)['mode']}))
