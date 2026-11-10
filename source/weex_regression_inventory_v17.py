from pathlib import Path
r=Path(__file__).resolve().parent
tokens=('tp_repair','external_tp_adoption','manual_position','live_new_entry_guard',
 'multi_symbol_ownership','position_protection_shadow','supervised_worker_recovery',
 'supervised_exit_policy','supervised_process_monitor','trading_modes')
for tok in tokens:
 print(tok, [p.stem for p in r.glob('test*.py') if tok in p.stem][:8])
