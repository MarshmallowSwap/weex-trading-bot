from pathlib import Path
import json
p=Path(r"D:\FUNDSHOT\weex_alerts\weex_ai_risk_config.json")
d=json.loads(p.read_text(encoding="utf-8"))
assert d["execution"]["enabled"] is False
assert d["risk"]["marginModePreference"]=="cross"
d["risk"]["leveragePreference"]="maximum_exchange_settable_per_symbol_cross"
d["risk"]["discretionaryLeverageReduction"]=False
d["risk"]["leverageTechnicalValidationRequired"]=True
t=p.with_suffix(".tmp")
t.write_text(json.dumps(d,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
t.replace(p)
r=json.loads(p.read_text(encoding="utf-8"))
print("leverage",r["risk"]["leveragePreference"],"discretionary",r["risk"]["discretionaryLeverageReduction"],"cross",r["risk"]["marginModePreference"],"live",r["execution"]["enabled"])
