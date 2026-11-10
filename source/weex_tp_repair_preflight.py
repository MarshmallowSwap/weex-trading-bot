"""Read-only live preflight for WEEX TP replacement, serialized with worker cycle.

This module has NO exchange write capability. It collects a fresh independent
account snapshot and history under the same OS lock as the live worker.
"""
from pathlib import Path
from weex_execution_cycle import exclusive
from weex_tp_repair_planner import plan

def preflight(root,reader=None,*,save_proposals=False):
    root=Path(root)
    with exclusive(root/'weex_live_worker.lock'):
        return plan(root,reader=reader,save_proposals=save_proposals)
