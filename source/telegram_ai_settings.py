"""Telegram WEEX AI Desk settings; configuration only, never places trades."""
import json,re,os
from decimal import Decimal,InvalidOperation
from pathlib import Path
from live_control import display as live_display
CONFIG=Path(__file__).with_name("weex_ai_risk_config.json")
PRESETS=("0.50","1.00","2.00","5.00")
def read():
    return json.loads(CONFIG.read_text(encoding="utf-8"))
def validate(raw):
    v=raw.strip().replace(",",".")
    if not re.fullmatch(r"[0-9]+(?:\.[0-9]{1,2})?",v):
        raise ValueError("Usa un importo positivo con massimo 2 decimali, es. 1,75")
    value=Decimal(v)
    if value<=0 or value>Decimal("100000"):
        raise ValueError("Inserisci un importo compreso tra 0,01 e 100000 USDT")
    return value
def save_profit(raw):
    amount=validate(raw)
    import live_control
    live_control.stop('tp_settings','telegram',CONFIG.parent)
    cfg=read()
    fixed=cfg["telegramSettings"]["fixedProfit"]
    fixed["enabled"]=True
    fixed["targetNetProfitUSDT"]=float(amount)
    fixed["reference"]="gross_price_pnl_before_entry_exit_fees_slippage_and_funding"
    settings=cfg.setdefault("strategySettings", {})
    settings["targetNetProfitUSDT"]=float(amount)
    settings["tpMode"]="fixed"
    settings["tpAccountingMode"]="GROSS_BEFORE_COSTS"
    tmp=CONFIG.with_suffix(".temp")
    tmp.write_text(json.dumps(cfg,indent=2,ensure_ascii=False),encoding="utf-8")
    os.replace(tmp,CONFIG)
    return amount
def message():
    c=read()
    p=c["telegramSettings"]["fixedProfit"]
    from weex_trailing import description
    gross=c['strategySettings'].get('tpAccountingMode')=='GROSS_BEFORE_COSTS'
    kind='lordo' if gross else 'netto'
    reference=("Prima di commissioni, slippage e funding"
               if gross else "Oltre break-even, commissioni stimate incluse")
    return ("⚙️ WEEX AI DESK — TP\n"
            f"🎯 Obiettivo {kind}: +{Decimal(str(p['targetNetProfitUSDT'])):.2f} USDT\n"
            f"📌 Riferimento: {reference}\n"
            +description(c['strategySettings'])+"\n"
            +"🛑 Stop Loss: OFF\n"
            f"{live_display()}\n\n"
            "Premi 'Imposta TP in USDT' per usare il tastierino.")
def keyboard():
    return {"inline_keyboard":[
        [{"text":"+0,50 USDT","callback_data":"aitp:0.50"},{"text":"+1,00 USDT","callback_data":"aitp:1.00"}],
        [{"text":"+2,00 USDT","callback_data":"aitp:2.00"},{"text":"+5,00 USDT","callback_data":"aitp:5.00"}],
        [{"text":"+20,00 USDT lordi","callback_data":"aitp:20.00"}],
        [{"text":"✏️ Personalizzato","callback_data":"aitp:custom"}],
        [{"text":"🔄 Stato impostazioni","callback_data":"aitp:show"}]
    ]}
