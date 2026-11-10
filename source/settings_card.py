"""Dynamic Telegram settings card from WEEX local configuration."""
from pathlib import Path
from datetime import datetime
from decimal import Decimal
from PIL import Image,ImageDraw,ImageFont,ImageFilter
import json,math
from live_control import display as live_display
ROOT=Path(__file__).resolve().parent
OUT=ROOT/"settings_live.png"
def f(size,bold=False):
 return ImageFont.truetype("C:/Windows/Fonts/"+("segoeuib.ttf" if bold else "segoeui.ttf"),size)
def render():
 c=json.loads((ROOT/"weex_ai_risk_config.json").read_text(encoding="utf-8"))
 strat=c.get("strategySettings",{})
 fixed=c["telegramSettings"]["fixedProfit"]
 pos=c["telegramSettings"]["maxConcurrentPositions"]["default"]
 im=Image.new("RGB",(1080,1270),(5,12,27));d=ImageDraw.Draw(im)
 for y in range(1270):
  k=y/1270
  d.line((0,y,1080,y),fill=(int(5+2*k),int(13+9*k),int(28+21*k)))
 for x in range(40,1080,60):
  d.line((x,210,x+140,930),fill=(11,35,61),width=1)
 def panel(box,edge=(26,126,183),fill=(11,28,51)):
  layer=Image.new("RGBA",im.size);ld=ImageDraw.Draw(layer)
  ld.rounded_rectangle(box,radius=24,outline=(*edge,150),width=7)
  blur=layer.filter(ImageFilter.GaussianBlur(16))
  im.paste(blur,(0,0),blur)
  ImageDraw.Draw(im).rounded_rectangle(box,radius=24,outline=edge,fill=fill,width=3)
 def txt(x,y,s,size=27,color=(231,243,252),bold=False):
  ImageDraw.Draw(im).text((x,y),str(s),font=f(size,bold),fill=color)
 cyan=(40,212,255);green=(46,222,167);gray=(147,177,202);orange=(255,169,78)
 panel((30,28,1050,205),cyan,(9,31,56))
 txt(65,58,"WEEX",68,bold=True)
 txt(300,58,"AI DESK",68,cyan,True)
 txt(70,150,"TRADING SETTINGS / CONTROL PANEL",25,gray)
 txt(812,162,datetime.now().strftime("%d/%m %H:%M"),20,cyan)
 panel((35,243,1045,465),cyan)
 txt(72,266,"TAKE PROFIT",30,gray,True)
 txt(74,318,str(strat.get("tpMode","fixed")).upper(),48,cyan,True)
 txt(575,322,"+%.2f USDT"%Decimal(str(fixed["targetNetProfitUSDT"])),43,green,True)
 txt(75,397,"Target fisso netto oltre Break Even (stimato)",23,gray)
 panel((35,488,1045,696),(79,117,167))
 txt(72,516,"STOP LOSS / MODELLO",30,gray,True)
 smode=str(strat.get("slMode","off")).upper()
 txt(74,570,smode,52,orange if smode=="OFF" else cyan,True)
 txt(470,575,"NON PROTETTIVO",30,orange,True)
 txt(74,647,"Nessun ordine stop attivo su WEEX",20,gray)
 panel((35,721,529,926),cyan)
 txt(62,752,"COSTO / APERTURA",26,gray,True)
 txt(63,815,str(c["risk"].get("orderCostTargetUSDT",5))+" USDT",48,(245,248,255),True)
 txt(62,882,"Margine + fee; SUSDT in demo",20,gray)
 panel((548,721,1045,926),cyan)
 txt(575,752,"MAX POSIZIONI",26,gray,True)
 txt(575,815,str(pos)+" / 10",48,(245,248,255),True)
 panel((35,951,1045,1104),(255,88,111),(46,19,37))
 txt(72,979,"AUTOMATED LIVE TRADING",31,bold=True)
 txt(73,1033,live_display(),28,(255,119,135),True)
 txt(62,1146,"I pulsanti Telegram modificano la configurazione.",23,gray)
 txt(62,1190,"Avvio e stop: /live_start, /live_stop. Stato: /live_status.",19,gray)
 temp=OUT.with_suffix(".temp.png")
 im.save(temp);temp.replace(OUT)
 return OUT
if __name__=="__main__":
 p=render();print("rendered",p.name,p.stat().st_size)
