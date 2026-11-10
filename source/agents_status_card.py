"""Dynamic WEEX Telegram status graphic, based only on observed local state."""
import json,math,random
from datetime import datetime,timezone
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont,ImageFilter
ROOT=Path(__file__).resolve().parent
OUT=ROOT/"agents_status_live.png"
AGENT_CARDS=(
 ("TREND AGENT","trend"),("MOMENTUM AGENT","momentum"),
 ("LIQUIDITY AGENT","liquidity"),("RISK GUARDIAN","risk"),
 ("EXECUTION AGENT","execution"),("EXIT AGENT","exit"),
 ("POSITION MANAGER","positions"),("SHADOW ORCHESTRATOR","orchestrator"),
)
MODULE_LABELS={
 'ENTRY_CHECKS_PENDING':'CONTROLLI PRIMA DELL INGRESSO',
 'WAIT_API_BUDGET':'ATTESA BUDGET API','WAIT_ACCOUNT_OBSERVATION':'ATTESA LETTURA CONTO',
 'ON_CONFIRMED_FILL':'NUOVI TP: DOPO IL FILL','READY_ANALYSIS':'ANALISI PRONTA',
 'READY_READ_ONLY':'CONTROLLI SOLA LETTURA','READY_SHADOW':'COORDINAMENTO SHADOW',
 'BLOCKED_UNITS':'BOOK LETTO / UNITA DA VERIFICARE',
 'VALIDATION_ONLY':'RUNNER: VERIFICHE SENZA ORDINI',
 'PARTIAL_COVERAGE':'BOOK: COPERTURA PARZIALE','DISABLED_BY_USER':'DISABILITATO SU RICHIESTA',
 'PREVIEW_ONLY':'TP CALCOLATO / NON ATTIVO','NOT_OBSERVED':'NESSUN TP NEL CICLO',
 'STALE':'DATI NON RECENTI','DEGRADED':'DATI INCOMPLETI','MISSING':'DATI ASSENTI',
 'CONFIG_UNSAFE':'CONFIGURAZIONE DA VERIFICARE',
 'STALE_OR_INCOMPLETE':'DATI POSIZIONI INCOMPLETI',
 'STALE_OR_DEGRADED':'COORDINAMENTO NON RECENTE',
}
READY_STATES={'READY_ANALYSIS','READY_READ_ONLY','READY_SHADOW'}
def module_status_label(state):
 return MODULE_LABELS.get(state,'NON VERIFICATO')
def font(n,b=False):
 p="C:/Windows/Fonts/"+("seguisb.ttf" if b else "segoeui.ttf")
 return ImageFont.truetype(p,n)
def read_status(name,key,limit):
 try:
  obj=json.loads((ROOT/name).read_text(encoding="utf-8"))
  ts=datetime.fromisoformat(obj[key].replace("Z","+00:00"))
  age=(datetime.now(timezone.utc)-ts).total_seconds()/3600
  return ("OK" if 0<=age<=limit else "STALE"),ts,obj
 except Exception:return "ERROR",None,{}

def scanner_status(age_status,report):
 if age_status!='OK':return age_status
 errors=[r.get('error') for r in report.get('results',[]) if r.get('decision')=='ERROR']
 errors += [(r.get('realOrderBook') or {}).get('reason') for r in report.get('results',[])
            if (r.get('realOrderBook') or {}).get('status')=='ERROR']
 if errors:return 'WAIT' if all(e=='BudgetDeferred' for e in errors) else 'ERROR'
 return 'OK' if report.get('analysisComplete') is True else 'ERROR'
def render():
 cfg=json.loads((ROOT/"weex_ai_risk_config.json").read_text(encoding="utf-8"))
 a,at,scan=read_status("market_agents_latest.json","asOf",12/60)
 a=scanner_status(a,scan)
 b,bt,strategy=read_status("market_agents_latest.json","asOf",12/60)
 from agent_health import assess,assess_agents
 health=assess()
 readiness=assess_agents()
 if health["status"]!="OK": b=health["status"]
 if b in ("WAIT_API_BUDGET","WAIT_ACCOUNT_OBSERVATION"):b="WAIT"
 W,H=1080,1350
 im=Image.new("RGB",(W,H),(4,8,21));p=im.load()
 for y in range(H):
  for x in range(W):
   beam=max(0,1-abs(x-W*.64)/(W*.7))
   glow=max(0,1-abs(y-220)/650)
   p[x,y]=(int(4+5*glow),int(9+13*beam*glow),int(22+22*beam*glow))
 d=ImageDraw.Draw(im)
 cyan=(44,218,255); muted=(149,174,202);white=(237,246,255)
 def glowbox(box,radius,stroke,fill=(10,24,47)):
  layer=Image.new("RGBA",(W,H));ld=ImageDraw.Draw(layer)
  ld.rounded_rectangle(box,radius=radius,outline=(*stroke,180),width=5)
  blurred=layer.filter(ImageFilter.GaussianBlur(16))
  im.paste(blurred,(0,0),blurred)
  dr=ImageDraw.Draw(im);dr.rounded_rectangle(box,radius=radius,fill=fill,outline=stroke,width=3)
 def label(x,y,text,size,color,bold=False):
  ImageDraw.Draw(im).text((x,y),str(text),font=font(size,bold),fill=color)
 # ornamental chart background
 rnd=random.Random(28)
 d=ImageDraw.Draw(im)
 for i in range(27):
  x=25+i*39;mid=255+int(35*math.sin(i*.77));hi=rnd.randint(20,82)
  d.line((x,mid-hi,x,mid+hi),fill=(16,66,104),width=3)
  d.rounded_rectangle((x-8,mid-hi//2,x+8,mid+hi//3),radius=2,fill=(15,74,115))
 glowbox((36,38,1044,252),28,(11,188,243),(8,26,54))
 label(81,67,"WEEX",74,white,True);label(332,67,"AI DESK",74,cyan,True)
 label(86,166,"AGENT STATUS  /  LIVE SYSTEM TELEMETRY",23,(118,203,236))
 label(798,204,datetime.now().strftime("%d/%m/%Y %H:%M"),17,muted)
 def status_card(y,headline,status,detail,accent):
  glowbox((37,y,1043,y+175),23,accent,(9,25,45))
  dr=ImageDraw.Draw(im)
  dr.ellipse((68,y+40,151,y+123),outline=accent,width=7)
  if status=='OK':
   dr.line([(89,y+81),(105,y+98),(132,y+65)],fill=accent,width=6)
  else:
   label(99,y+52,'!',44,accent,True)
  label(189,y+30,headline,32,white,True)
  label(191,y+88,detail,23,muted)
  dr.rounded_rectangle((851,y+52,1004,y+107),radius=16,fill=(22,44,62),outline=accent,width=2)
  label(883,y+64,"WAIT" if status.startswith("WAIT_") else status,25,accent,True)
 def color(s):return (42,232,162) if s=="OK" else (255,179,72) if s in ("STALE","WAIT","WAIT_API_BUDGET","WAIT_ACCOUNT_OBSERVATION") else (255,83,113)
 status_card(291,"MARKET SCANNER",a,("Ultimo scan: "+at.astimezone().strftime("%d/%m %H:%M") if at else "Dati non disponibili")+"  |  "+str(scan.get("universeSize",len(scan.get("results",[]))))+" coppie",color(a))
 status_card(486,"STRATEGY DIAGNOSTICS",b,("Ultima analisi: "+bt.astimezone().strftime("%d/%m %H:%M") if bt else "Dati non disponibili"),color(b))
 label(58,702,"AI SYSTEM / MODULE STATUS  •  "+("WAIT" if health["status"].startswith("WAIT_") else health["status"]),28,color(health["status"]),True)
 modules=readiness['modules']
 for k,(name,key) in enumerate(AGENT_CARDS):
  x=40+(k%2)*510;y=748+(k//2)*82
  glowbox((x,y,x+492,y+70),15,(45,81,119),(10,25,45))
  label(x+25,y+8,name,20,white,True)
  record=modules.get(key,{})
  state=record.get('state')
  status_text=module_status_label(state)
  label(x+26,y+39,status_text,15,(42,232,162) if state in READY_STATES else (145,159,181))
 from live_control import state as live_state
 live=live_state()["mode"]=="RUNNING"
 glowbox((38,1120,1042,1226),20,(255,80,105) if not live else (255,170,70),(44,17,34))
 label(72,1145,"AUTOMATED ORDERS",31,white,True)
 label(665,1145,"STOPPED" if not live else "ENABLED",32,(255,102,123) if not live else (255,178,66),True)
 label(65,1260,"COSTO "+str(cfg["risk"].get("orderCostTargetUSDT",cfg["risk"]["initialMarginTargetUSDT"]))+" USDT     •     MAX "+str(cfg["telegramSettings"]["maxConcurrentPositions"]["default"])+" POSIZIONI     •     DATI REALI",20,(136,182,211))
 tmp=OUT.with_name("agents_status_live.tmp.png")
 im.save(tmp,format="PNG");tmp.replace(OUT)
 return OUT,{"scanner":a,"strategy":b,"live":live,"analysisReady":readiness['analysisReady'],"liveReady":False}
if __name__=="__main__":
 print(render()[1])
