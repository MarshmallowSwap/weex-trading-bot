"""Authorization and recovery path diagnosis. Does not request a start or trade."""
import json, datetime
from pathlib import Path
import live_control
from weex_supervised_entry_authority_bridge_v8 import ready as bridge_ready
from weex_supervised_exit_policy_v7 import status as exit_status
from weex_supervised_crash_entry_child_v5 import supervisor_ready
from weex_supervised_crash_watchdog_v4 import has_unknown_entry
from weex_supervised_crash_executor_v2 import CLIENT_ID
ROOT=Path(__file__).resolve().parent
r={'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
   'mainSwitch':live_control.state(ROOT),
   'codeIntegrityErrors':live_control.build_errors(ROOT),
   'releaseGateErrors':live_control.release_gate_errors(ROOT),
   'startReadinessErrors':live_control.readiness(ROOT),
   'supervisorReady':supervisor_ready(ROOT),
   'bridge':bridge_ready(ROOT),
   'exitPolicy':exit_status(ROOT),
   'durableUnknownEntry':has_unknown_entry(ROOT,CLIENT_ID),
   'networkWrites':0,'liveModeChanged':False}
print(json.dumps(r,ensure_ascii=False))
