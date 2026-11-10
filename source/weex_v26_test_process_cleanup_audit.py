import subprocess,json
query=r"""Get-CimInstance Win32_Process -Filter "Name='python.exe' OR Name='pythonw.exe'" | Where-Object { $_.CommandLine -match 'NO_PENDING_CRASH_INTENT|supervisor_os_crash_restart_v26' } | Select-Object ProcessId,ParentProcessId,Name | ConvertTo-Json -Compress"""
r=subprocess.run(['powershell','-NoProfile','-Command',query],capture_output=True,text=True,timeout=15)
print(json.dumps({'returncode':r.returncode,'matchingTestProcesses':json.loads(r.stdout) if r.stdout.strip() else [],'errorType':None if r.returncode==0 else 'PROCESS_QUERY_FAILED'}))
