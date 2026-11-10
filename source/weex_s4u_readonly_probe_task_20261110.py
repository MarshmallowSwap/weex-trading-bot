"""No-trade S4U scheduler probe; run only from temporary noninteractive task."""
from pathlib import Path
import json,os,time
p=Path(__file__).resolve().parent/'weex_s4u_probe_executed_20261110.json'
temp=p.with_name(p.name+'.tmp')
temp.write_text(json.dumps({'pid':os.getpid(),'epoch':time.time(),
   'user':os.environ.get('USERNAME'),'taskExecuted':True,'exchangeWrites':0,
   'productionConfigChanged':False},sort_keys=True),encoding='utf-8')
os.replace(temp,p)
