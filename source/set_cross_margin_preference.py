from pathlib import Path
import json
root=Path(r"D:\FUNDSHOT\weex_alerts")
p=root/"weex_ai_risk_config.json"
cfg=json.loads(p.read_text(encoding="utf-8"))
previous=cfg["risk"]["marginModePreference"]
cfg["risk"]["marginModePreference"]="cross"
cfg["risk"]["crossMarginSharedCollateralWarning"]="Cross uses shared available account collateral; liquidation losses may affect other open positions."
assert cfg["execution"]["enabled"] is False
tmp=p.with_suffix(".json.tmp")
tmp.write_text(json.dumps(cfg,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
tmp.replace(p)
print("marginPreference",previous,"->",cfg["risk"]["marginModePreference"],"executionEnabled",cfg["execution"]["enabled"])
