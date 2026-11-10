import json
from pathlib import Path
p=Path(__file__).parent
cfg=json.loads((p/"weex_ai_risk_config.json").read_text(encoding="utf-8"))
checks={
 "scanner_snapshot":(p/"universe_latest.json").exists(),
 "telegram_commands":(p/"commands.py").exists(),
 "settings_renderer":(p/"settings_card.py").exists(),
 "agents_renderer":(p/"agents_status_card.py").exists(),
 "breakeven_resolver":(p/"break_even_resolver.py").exists(),
 "strategy_calculator":(p/"tp_sl_strategy_engine.py").exists(),
 "trailing_state_store":False,
 "autonomous_agent_heartbeat":False,
 "account_tier_leverage_verification":False,
 "live_execution_idempotency":False,
 "exchange_order_reconciliation":False,
 "protective_order_failover":False,
}
print("WEEX READINESS AUDIT")
for name,ok in checks.items():print(("PASS" if ok else "BLOCKED"),name)
print("real_execution_enabled",cfg.get("execution",{}).get("enabled"))
print("no_live_orders_submitted_by_this_audit",True)
