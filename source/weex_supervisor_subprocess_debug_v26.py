import tempfile,subprocess,sys,time,json
from pathlib import Path
from test_weex_supervisor_os_crash_restart_v26 import CHILD,SOURCE,HEALTH
with tempfile.TemporaryDirectory() as td:
 p=subprocess.Popen([sys.executable,'-B','-c',CHILD,td],cwd=str(SOURCE),stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
 time.sleep(1)
 path=Path(td)/HEALTH
 print('PARENT_REPORTED_PID',p.pid,'POLL',p.poll())
 print('HEALTH',path.read_text(encoding='utf-8')[:1000] if path.exists() else 'MISSING')
 p.kill();p.communicate(timeout=3)
