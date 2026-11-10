from pathlib import Path
r=Path(__file__).resolve().parent
terms=('Budget(','.reserve(','budget_request(','.observe(','requests_mock','MockResponse','status_code=200')
for f in sorted(r.glob('test*.py')):
 try:t=f.read_text(encoding='utf-8')
 except UnicodeError:continue
 hits=[v for v in terms if v in t]
 if hits and any(k in f.name for k in ('budget','api','transport','recovery','supervised','http','scan')):
  print('FILE',f.name,'MATCHES',','.join(hits))
  for i,line in enumerate(t.splitlines(),1):
   if any(q in line for q in ('Budget(','.reserve(','budget_request(','.observe(','status_code=200')):
    print(' LINE',i,line[:170])
