from pathlib import Path
import json
p=Path(r"D:\FUNDSHOT\weex_alerts\weex_ai_risk_config.json")
c=json.loads(p.read_text(encoding="utf-8"))
c["strategySettings"]={
 "tpMode":"fixed","slMode":"off","implementationState":"calculation_only",
 "marginUSDT":5,"targetNetProfitUSDT":c["telegramSettings"]["fixedProfit"]["targetNetProfitUSDT"],
 "tpRoiPercent":20,"slLossPercent":25,"atrTakeMultiplier":2,"atrStopMultiplier":2,
 "minProfitUSDT":0.5,"fixedStopPrice":None,
 "trailingActivationProfitUSDT":0.5,"trailingAtrDistance":1.5}
p.write_text(json.dumps(c,ensure_ascii=False,indent=2),encoding="utf-8")
print("strategy config ready, execution disabled:",not c["execution"]["enabled"])
