"""Demo submission is blocked until independent operational certification.
Flags passed by callers cannot authorize an order.
"""
from demo_e2e_evidence import run as evidence_run
from demo_intent_binding import register,uncertain
from weex_demo_transport import DemoTransport
def attempt(payload,*,db_path=None,transport=None,exit_verified=False,binding_verified=False):
 evidence=evidence_run()
 if evidence.get("ready") is not True:
  return {"submitted":False,"reason":"EXCHANGE_E2E_NOT_CERTIFIED","failedChecks":[k for k,v in evidence["checks"].items() if not v]}
 # The actual transport remains write-disabled until a separate reviewed deployment.
 return {"submitted":False,"reason":"DEMO_TRANSPORT_DISABLED"}
