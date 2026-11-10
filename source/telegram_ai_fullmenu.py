import json,os,re

from pathlib import Path

from decimal import Decimal

from live_control import display as live_display
from weex_trading_modes import get_mode

P=Path(__file__).with_name("weex_ai_risk_config.json")

def load():return json.loads(P.read_text(encoding="utf-8"))

def save(c):

 t=P.with_suffix(".tmp");t.write_text(json.dumps(c,indent=2,ensure_ascii=False),encoding="utf-8");os.replace(t,P)

def set_positions(value):

 n=int(value)

 if n<1 or n>10:raise ValueError("Posizioni: valore ammesso da 1 a 10")

 c=load();c["telegramSettings"]["maxConcurrentPositions"]["default"]=n;save(c);return n

def set_sl(enabled):

 c=load();c["risk"]["stopLoss"]["enabled"]=bool(enabled)

 if enabled:c["risk"]["stopLoss"]["mode"]="pending_configuration"

 else:

  c["risk"]["stopLoss"]["mode"]="optional"

  c["strategySettings"]["slMode"]="off"

 save(c)

 return bool(enabled)

def summary():

 c=load(); p=c["telegramSettings"]["fixedProfit"]

 n=c["telegramSettings"]["maxConcurrentPositions"]["default"]

 sl=c["risk"]["stopLoss"]

 return ("⚙️ WEEX AI DESK — IMPOSTAZIONI\n\n"

         f"🎯 TP modello: {c.get('strategySettings',{}).get('tpMode','fixed').upper()} | TP +{Decimal(str(p['targetNetProfitUSDT'])):.2f} USDT {'lordi' if c['strategySettings'].get('tpAccountingMode')=='GROSS_BEFORE_COSTS' else 'netti'}\n"

         "💰 Netto stimato al TP: visibile nella scheda della singola posizione dopo l'ingresso; include le fee stimate, non garantisce esecuzione o funding.\n"

         f"📊 Limite posizioni automatiche: {n}/10\n"

         f"🛑 SL modello: {c.get('strategySettings',{}).get('slMode','off').upper()} (non protettivo)\n"

         f"💰 Costo per apertura: {c['risk'].get('orderCostTargetUSDT', 5)} USDT (margine + commissione; SUSDT in demo)\n"

         f"{live_display()}\n\nLe impostazioni valgono per i nuovi ingressi.")

def home_text():
 return "🤖 WEEX AI DESK\n\n"+live_display()+"\nScegli una categoria:"

def menu():
 from telegram_button_menu import home
 return home()

def trading_menu():
 from telegram_button_menu import trading
 return trading()

def trading_mode_menu():
 mode=get_mode(Path(__file__).resolve().parent)['mode']
 labels={'automatic':'✅ Automatico' if mode=='automatic' else 'Automatico',
         'alerts_only':'✅ Solo alert' if mode=='alerts_only' else 'Solo alert',
         'automatic_manual':'✅ Automatico + manuale' if mode=='automatic_manual' else 'Automatico + manuale',
         'manual_only':'✅ Solo manuale' if mode=='manual_only' else 'Solo manuale'}
 return {"inline_keyboard":[
  [{"text":labels['automatic'],"callback_data":"tradingmode:set:automatic"}],
  [{"text":labels['alerts_only'],"callback_data":"tradingmode:set:alerts_only"}],
  [{"text":labels['automatic_manual'],"callback_data":"tradingmode:set:automatic_manual"}],
  [{"text":labels['manual_only'],"callback_data":"tradingmode:set:manual_only"}],
  [{"text":"▶ Prepara avvio LIVE","callback_data":"livectl:start"}],
  [{"text":"⬅️ Torna a Trading","callback_data":"aimenu:trade"}]
 ]}

def trading_mode_text():
 mode=get_mode(Path(__file__).resolve().parent)['mode']
 text={'automatic':'Automatico: il runner valuta e apre i segnali validi.',
       'alerts_only':'Solo alert: scansione e notifiche proseguono, nuovi ingressi disabilitati.',
       'automatic_manual':'Automatico + manuale: scansione automatica e ordini espliciti con `TOKEN LONG` o `TOKEN SHORT`.',
       'manual_only':'Solo manuale: apre soltanto dalle tue richieste: pulsante Apri posizione manuale o comandi TOKEN LONG / TOKEN SHORT. Usa costo, leva e TP configurati; gestione delle posizioni e riconciliazione restano attive. La scansione continua per gli alert.'}
 return 'Modalità ingressi\n\n'+text[mode]+'\n\nCambiare modalità ferma i nuovi ingressi: torna a Trading, premi Prepara avvio LIVE e conferma.'

def monitoring_menu():
 from telegram_button_menu import monitoring
 return monitoring()

def positions_menu():
 from telegram_button_menu import button,keyboard,nav
 return keyboard(*[[button(str(i),f'aipos:{i}') for i in range(k,min(k+5,11))] for k in (1,6)],nav('desk:settings'))

def select_strategy(kind, mode):

 allowed={"tp":("fixed","dynamic","percent","trailing","hybrid"),"sl":("off","fixed","percent","atr","trailing","ai")}

 if kind not in allowed or mode not in allowed[kind]:raise ValueError("Invalid mode")

 c=load()

 k="tpMode" if kind=="tp" else "slMode"

 if kind=="sl" and mode=="fixed" and not c["strategySettings"].get("fixedStopPrice"):

  raise ValueError("SL prezzo fisso richiede prima un prezzo valido: non selezionato")

 c["strategySettings"][k]=mode
 if kind=='tp':
  c["strategySettings"]['tpAccountingMode']='GROSS_BEFORE_COSTS' if mode=='fixed' else 'NET'

 # SL is a theoretical model setting, never claim protective execution.

 c["risk"]["stopLoss"]["enabled"]=False

 save(c)

 return mode

def tp_modes_menu():
 from telegram_button_menu import button,keyboard,nav
 mode=load().get('strategySettings',{}).get('tpMode','fixed')
 return keyboard(
  [button(('✅ ' if mode=='fixed' else '')+'TP fisso lordo','aitpmode:fixed')],
  [button(('✅ ' if mode=='trailing' else '')+'TP netto + trailing WEEX','aitpmode:trailing')],
  [button('💵 Imposta TP in USDT','desk:tp_gross')],
  [button('▶ Prepara avvio LIVE','livectl:start')],
  [button('Modelli teorici · non LIVE','desk:models')],nav('desk:settings'))

def sl_menu():
 from telegram_button_menu import button,keyboard,nav
 return keyboard([button('Conferma SL OFF','aisl:off')],
                 [button('Modelli teorici · nessuno stop reale','desk:slmodels')],nav('desk:settings'))


def sl_calculation_menu():
 from telegram_button_menu import button,keyboard,nav
 return keyboard(*[[button(label+' · calcolo','aisl:'+mode)] for mode,label in
                   [('fixed','Prezzo fisso'),('percent','Percentuale'),('atr','ATR dinamico'),('trailing','Trailing'),('ai','Dinamico AI')]],
                 [button('Ripristina SL OFF','aisl:off')],nav('desk:models'))
