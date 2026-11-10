from pathlib import Path
root=Path(r'D:\FUNDSHOT\weex_alerts')
for p in root.iterdir():
 if p.is_file() and ('bot' in p.name.lower() and 'v2' in p.name.lower()):print(p.name)
