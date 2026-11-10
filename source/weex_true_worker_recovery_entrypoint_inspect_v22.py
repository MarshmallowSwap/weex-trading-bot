from pathlib import Path
p=Path(__file__).resolve().parent/'weex_live_worker.py'
lines=p.read_text(encoding='utf-8').splitlines()
for i,line in enumerate(lines):
 if ('supervised-crash-recovery' in line or 'WORKER_RESTART_PROTECTED_ENTRY_VERIFIED' in line or 'RECOVERY_READBACK_UNCERTAIN' in line):
  print('MATCH',i+1)
  for j in range(max(0,i-12),min(len(lines),i+23)):print(j+1,lines[j])
