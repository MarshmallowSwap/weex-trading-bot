"""End-to-end socket-level lost HTTP response with actual pilot journal.

Localhost server accepts exactly one fake protected WEEX pilot order, records
the order, and drops the HTTP connection before returning an ACK. The real
guarded dispatcher journals OUTCOME_UNKNOWN. Fresh subprocess refuses resend;
GET finds the accepted order. NO WEEX credentials, NO exchange calls.
"""
import http.server,json,subprocess,sys,tempfile,threading,unittest
from urllib.request import urlopen
from pathlib import Path
from contextlib import closing
from weex_isolated_pilot_offline_journal import reserve,connect
from weex_pilot_attach_atomic_stop import attach
from weex_pilot_dispatch_readback_run import pending

ROOT=Path(__file__).resolve().parent
CHILD="""
import sys,json
from urllib.request import Request,urlopen
from pathlib import Path
from weex_pilot_guarded_entry_dispatch import send_entry_once
from weex_pilot_protected_entry_sdk import ProtectedEntryTransport
class LocalLostAck(ProtectedEntryTransport):
 def preflight_entry(self,*a,**kw):return True
 def send_entry_only(self,op,payload,*,ask,account):
  data=json.dumps(payload).encode()
  request=Request('http://127.0.0.1:'+sys.argv[2]+'/order',
    data=data,headers={'Content-Type':'application/json'},method='POST')
  with urlopen(request,timeout=3) as res:return json.load(res)
r=send_entry_once(Path(sys.argv[1]),'P',ask='2200',account={},
                  transport=LocalLostAck(Path(sys.argv[1]).parent))
print(json.dumps(r))
"""
RESTART="""
import json,sys
from pathlib import Path
from weex_pilot_guarded_entry_dispatch import send_entry_once
from weex_pilot_protected_entry_sdk import ProtectedEntryTransport
from weex_pilot_dispatch_readback_run import pending
class NeverSend(ProtectedEntryTransport):
 def preflight_entry(self,*a,**k):raise AssertionError('DUPLICATE_PREFLIGHT')
 def send_entry_only(self,*a,**k):raise AssertionError('DUPLICATE_ORDER')
db=Path(sys.argv[1])
r=send_entry_once(db,'P',ask='2200',account={},transport=NeverSend(db.parent))
print(json.dumps({'dispatch':r,'pending':pending(db)}))
"""
class LostAckHTTP(unittest.TestCase):
 def test_received_http_post_lost_response_restart_never_duplicates(self):
  accepted=[]
  class Handler(http.server.BaseHTTPRequestHandler):
   def do_POST(self):
    if self.path!='/order':self.send_error(404);return
    data=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
    accepted.append(data)
    self.close_connection=True
    # Deliberately no HTTP response, as if a completed request timed out.
   def do_GET(self):
    if self.path!='/order/history':self.send_error(404);return
    doc=json.dumps([{'clientOrderId':x['newClientOrderId'],
      'orderId':'OFFLINE-TEST-ORDER-1','status':'FILLED'} for x in accepted]).encode()
    self.send_response(200);self.send_header('Content-Length',str(len(doc)))
    self.end_headers();self.wfile.write(doc)
   def log_message(self,*a):pass
  server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler)
  threading.Thread(target=server.serve_forever,daemon=True).start()
  try:
   with tempfile.TemporaryDirectory() as td:
    db=Path(td)/'p.sqlite3'
    reserve(db,pilot_id='P',side='LONG',quantity='.002',stop_price='2150')
    attach(db,'P',stop='2150',reference_price='2200')
    first=subprocess.run([sys.executable,'-c',CHILD,str(db),str(server.server_port)],
      cwd=ROOT,text=True,capture_output=True,timeout=20,check=True)
    self.assertEqual(json.loads(first.stdout)['state'],'OUTCOME_UNKNOWN')
    self.assertEqual(len(accepted),1)
    second=subprocess.run([sys.executable,'-c',RESTART,str(db)],
      cwd=ROOT,text=True,capture_output=True,timeout=20,check=True)
    state=json.loads(second.stdout)
    self.assertEqual(state['dispatch']['state'],'ALREADY_RESERVED_NO_RETRY')
    self.assertEqual(state['pending'],[['P','entry']])
    with closing(connect(db)) as conn:
     client=conn.execute('SELECT entry_id FROM pilot_v1').fetchone()[0]
    with urlopen('http://127.0.0.1:'+str(server.server_port)+'/order/history') as response:
     evidence=json.load(response)
    self.assertEqual(evidence,[{'clientOrderId':client,
      'orderId':'OFFLINE-TEST-ORDER-1','status':'FILLED'}])
    self.assertEqual(len(accepted),1,'DUPLICATE_POST_AFTER_RESTART')
  finally:
   server.shutdown();server.server_close()
if __name__=='__main__':unittest.main()
