import subprocess,sys
from pathlib import Path
root=Path(__file__).resolve().parent
cmd=f'"{sys.executable}" "{root / "weex_agent_orchestrator.py"}"'
for args in [["schtasks.exe","/Create","/F","/SC","MINUTE","/MO","15","/TN","WEEX_AI_Shadow_Orchestrator","/TR",cmd],["schtasks.exe","/Run","/TN","WEEX_AI_Shadow_Orchestrator"]]:
 p=subprocess.run(args,capture_output=True,text=True)
 print("returncode",p.returncode,(p.stdout+p.stderr).strip())
