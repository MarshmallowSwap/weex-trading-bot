import subprocess,json
try:
 ps='Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match "weex|market_agents|scan|python" } | Select-Object ProcessId,ParentProcessId,Name,CommandLine | ConvertTo-Json -Depth 3'
 p=subprocess.run(['powershell','-NoProfile','-Command',ps],capture_output=True,text=True,timeout=15)
 data=json.loads(p.stdout)
 if isinstance(data,dict):data=[data]
 print(json.dumps([{'pid':x.get('ProcessId'),'parent':x.get('ParentProcessId'),'name':x.get('Name'),'command':str(x.get('CommandLine') or '')[:180]} for x in data if 'python' in str(x.get('Name')).lower() or 'weex' in str(x.get('CommandLine')).lower()][:45]))
except Exception as e:print(type(e).__name__)
