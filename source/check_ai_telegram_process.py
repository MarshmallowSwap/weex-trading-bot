import subprocess,json
raw=subprocess.check_output(["powershell","-NoProfile","-Command","Get-CimInstance Win32_Process | Where-Object Name -Match 'python' | Select-Object ProcessId,CommandLine | ConvertTo-Json -Compress"],text=True)
for p in (lambda x:[x] if isinstance(x,dict) else x)(json.loads(raw)):
 cmd=p.get("CommandLine") or ""
 if "weex_alerts" in cmd and ("commands.py" in cmd or "monitor.py" in cmd):
  print("WEEX_PROCESS",p["ProcessId"],"commands" if "commands.py" in cmd else "monitor")
