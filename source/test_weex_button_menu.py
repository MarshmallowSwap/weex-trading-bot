import json
import sqlite3
import tempfile
import time
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

import live_control as control
import telegram_button_menu as ui
from weex_trading_modes import set_mode, connect


class ButtonMenuTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.config=json.loads(Path(__file__).with_name('weex_ai_risk_config.json').read_text(encoding='utf-8'))
        self.save_config()
        self.cfg={'telegram_chat_id':'7','telegram_user_id':'8'}
        set_mode(self.root,'manual_only','8')
        with closing(control.connect(self.root)) as c,c:
            c.execute("UPDATE switch_v1 SET mode='RUNNING'")
        p=patch.object(control,'readiness',return_value=[]);p.start();self.addCleanup(p.stop)

    def save_config(self):
        (self.root/'weex_ai_risk_config.json').write_text(json.dumps(self.config),encoding='utf-8')

    def update(self,data,user=8,chat=7,bot=False):
        return {'callback_query':{'id':'cb','data':data,'from':{'id':user,'is_bot':bot},
                                  'message':{'message_id':42,'chat':{'id':chat}}}}

    def tap(self,data,**kw):
        return ui.handle(self.update(data,**kw),self.cfg,self.root)

    def action(self,result,suffix):
        return next(b['callback_data'] for row in result['reply']['reply_markup']['inline_keyboard']
                    for b in row if b['callback_data'].endswith(':'+suffix))

    def type_value(self,result,value):
        for ch in value:result=self.tap(self.action(result,'sep' if ch==' ' else ch))
        return result

    def preview(self,side='LONG'):
        result=self.tap('desk:pick:manual:ETHUSDT')
        return self.tap(self.action(result,side))

    def queued(self):
        with closing(connect(self.root)) as c:
            return [dict(r) for r in c.execute('SELECT * FROM manual_requests_v1')]

    def test_all_home_categories_and_page_navigation(self):
        self.assertEqual(len(ui.home()['inline_keyboard']),5)
        for data in ('desk:settings','desk:recovery','desk:help','desk:models','desk:slmodels','desk:manual','desk:resolve'):
            result=self.tap(data)
            self.assertTrue(result['reply']['reply_markup']['inline_keyboard'],data)
        for markup in (ui.home(),ui.trading(),ui.monitoring(),ui.settings(),ui.recovery()):
            for row in markup['inline_keyboard']:
                for b in row:self.assertLessEqual(len(b['callback_data'].encode()),64)

    def test_unauthorized_chat_user_and_bot_cannot_create_editor_or_trade(self):
        for kw in ({'user':9},{'chat':9},{'bot':True}):
            result=self.tap('aimenu:cost',**kw);self.assertIsNone(result['reply'])
        self.assertFalse((self.root/'telegram_button_menu.sqlite3').exists())
        self.assertFalse(self.queued())

    def test_manual_preview_then_single_confirm_and_replay_after_restart(self):
        for side in ('LONG','SHORT'):
            # Distinct symbols so the existing durable per-symbol queue check is respected.
            symbol='ETHUSDT' if side=='LONG' else 'BTCUSDT'
            choice=self.tap('desk:pick:manual:'+symbol)
            result=self.tap(self.action(choice,side))
            self.assertIn(symbol+' '+side,result['reply']['text'])
            self.assertIn(str(self.config['risk']['orderCostTargetUSDT']),result['reply']['text'])
            self.assertEqual(len(self.queued()),0 if side=='LONG' else 1)
            confirm=self.action(result,'send')
            sent=self.tap(confirm);self.assertEqual(sent['manualRequest']['side'],side)
            # Every handle call reopens SQLite; replay protection survives process memory loss.
            self.assertNotIn('manualRequest',self.tap(confirm))
        self.assertEqual(len(self.queued()),2)

    def test_old_revision_cannot_repeat_digit_or_skip_preview(self):
        result=self.tap('aitpmode:amount');one=self.action(result,'1')
        self.tap(one);self.tap(one)
        with closing(ui._connect(self.root)) as c:
            row=c.execute('SELECT payload FROM wizard_v1 WHERE used=0').fetchone()
        self.assertEqual(json.loads(row['payload'])['value'],'1')
        preview=self.tap('desk:pick:manual:ETHUSDT')
        forged=self.action(preview,'LONG').rsplit(':',1)[0]+':send'
        self.assertNotIn('manualRequest',self.tap(forged));self.assertFalse(self.queued())

    def test_settings_change_invalidates_manual_confirmation(self):
        result=self.preview();confirm=self.action(result,'send')
        self.config['risk']['orderCostTargetUSDT']='17';self.save_config()
        result=self.tap(confirm)
        self.assertIn('cambiati',result['reply']['text']);self.assertFalse(self.queued())

    def test_stop_and_restart_generation_invalidates_manual_confirmation(self):
        confirm=self.action(self.preview(),'send')
        control.stop('8','7',self.root)
        with closing(control.connect(self.root)) as c,c:c.execute("UPDATE switch_v1 SET mode='RUNNING'")
        self.assertNotIn('manualRequest',self.tap(confirm));self.assertFalse(self.queued())

    def test_expired_cancelled_and_cross_user_confirmation_never_queue(self):
        confirm=self.action(self.preview(),'send')
        self.assertIsNone(self.tap(confirm,user=9)['reply'])
        with closing(ui._connect(self.root)) as c,c:c.execute('UPDATE wizard_v1 SET expires=0')
        self.assertNotIn('manualRequest',self.tap(confirm))
        confirm=self.action(self.preview(),'send');self.tap('desk:cancel')
        self.assertNotIn('manualRequest',self.tap(confirm));self.assertFalse(self.queued())

    def test_readiness_errors_and_wrong_mode_preserve_existing_guards(self):
        confirm=self.action(self.preview(),'send')
        with patch.object(control,'readiness',return_value=['CONTO_O_RECUPERO_DA_VERIFICARE']):
            result=self.tap(confirm)
        self.assertNotIn('manualRequest',result);self.assertIn('CONTO_O_RECUPERO',result['reply']['text'])
        set_mode(self.root,'automatic','8')
        self.assertIn('scegli Solo manuale',self.tap('desk:manual')['reply']['text'])
        self.assertFalse(self.queued())

    def test_gross_tp_button_configurable_without_order(self):
        settings=ui.settings()['inline_keyboard']
        self.assertTrue(any(b['callback_data']=='desk:tp_gross'
                            and 'USDT' in b['text'] for row in settings for b in row))
        editor=self.tap('desk:tp_gross')
        self.assertIn('lordo',editor['reply']['text'])
        before=(self.root/'weex_ai_risk_config.json').read_bytes()
        editor=self.type_value(editor,'20.75')
        self.assertEqual((self.root/'weex_ai_risk_config.json').read_bytes(),before)
        result=self.tap(self.action(editor,'ok'))
        self.assertIn('TP lordo',result['reply']['text'])
        config=json.loads((self.root/'weex_ai_risk_config.json').read_text(encoding='utf-8'))
        self.assertEqual(config['strategySettings']['targetNetProfitUSDT'],20.75)
        self.assertEqual(config['telegramSettings']['fixedProfit']['targetNetProfitUSDT'],20.75)
        self.assertEqual(config['strategySettings']['tpAccountingMode'],'GROSS_BEFORE_COSTS')
        self.assertEqual(config['strategySettings']['tpMode'],'fixed')
        self.assertEqual(control.state(self.root)['mode'],'STOPPED')
        self.assertFalse(self.queued())
        self.assertNotIn('manualRequest',self.tap(self.action(editor,'ok')))

    def test_cost_and_tp_decimal_keypads_update_config_only_after_save(self):
        for data,key,value in [('aimenu:cost','cost','7.50'),('aitpmode:amount','tp','20.25')]:
            before=(self.root/'weex_ai_risk_config.json').read_bytes()
            editor=self.type_value(self.tap(data),value)
            self.assertEqual((self.root/'weex_ai_risk_config.json').read_bytes(),before)
            confirm=self.action(editor,'ok');result=self.tap(confirm)
            self.assertIn(value,result['reply']['text'])
            after=json.loads((self.root/'weex_ai_risk_config.json').read_text(encoding='utf-8'))
            self.assertEqual(float(after['risk']['orderCostTargetUSDT'] if key=='cost' else after['strategySettings']['targetNetProfitUSDT']),float(value))
            self.assertEqual(control.state(self.root)['mode'],'STOPPED')
            self.assertNotIn('manualRequest',self.tap(confirm))
        self.assertFalse(self.queued())

    def test_invalid_amount_keeps_editor_without_saving(self):
        before=(self.root/'weex_ai_risk_config.json').read_bytes()
        editor=self.type_value(self.tap('aitpmode:amount'),'0')
        result=self.tap(self.action(editor,'ok'))
        self.assertIn('compreso',result['reply']['text'])
        result=self.tap(self.action(result,'clear'))
        result=self.type_value(result,'10')
        self.assertIn('10.00',self.tap(self.action(result,'ok'))['reply']['text'])
        self.assertNotEqual((self.root/'weex_ai_risk_config.json').read_bytes(),before)

    def test_custom_symbol_and_paginated_cached_universe(self):
        (self.root/'universe_latest.json').write_text(json.dumps({'symbols':[{'symbol':f'TOKEN{i}USDT'} for i in range(30)]}))
        result=self.tap('desk:symbols:manual:1');self.assertIn('2/3',result['reply']['text'])
        result=self.type_value(self.tap('desk:type:manual'),'TAO')
        result=self.tap(self.action(result,'ok'))
        self.assertIn('TAOUSDT',result['reply']['text']);self.assertFalse(self.queued())

    def test_reconciliation_order_ids_use_existing_validator_and_one_dispatch(self):
        result=self.type_value(self.tap('desk:ids:AAVEUSDT'),'123456789 987654321')
        confirm=self.action(result,'ok');result=self.tap(confirm)
        self.assertEqual(result['reconcileRequest']['orderIds'],['123456789','987654321'])
        self.assertEqual(result['reconcileRequest']['symbol'],'AAVEUSDT')
        self.assertNotIn('reconcileRequest',self.tap(confirm));self.assertFalse(self.queued())

    def test_maximum_five_order_ids_and_twenty_digits(self):
        for value in ('1 2 3 4 5 6','123456789012345678901'):
            result=self.type_value(self.tap('desk:ids:AAVEUSDT'),value)
            result=self.tap(self.action(result,'ok'))
            self.assertNotIn('reconcileRequest',result)
            self.assertIn('massimo 20',result['reply']['text'])

    def test_navigation_invalidates_outstanding_manual_confirm(self):
        confirm=self.action(self.preview(),'send')
        self.assertIsNone(self.tap('aimenu:home'))
        self.assertNotIn('manualRequest',self.tap(confirm));self.assertFalse(self.queued())

    def test_legacy_live_reply_and_reconcile_result_offer_buttons(self):
        from telegram_live_control import handle
        from weex_reconcile import keyboard
        reply=handle(self.update('livectl:stop'),self.cfg,self.root)['reply']
        self.assertTrue(reply['reply_markup']['inline_keyboard'])
        self.assertTrue(any(b['callback_data']=='desk:resolve' for row in keyboard({'items':[]})['inline_keyboard'] for b in row))

    def test_actual_polling_dispatches_confirmed_manual_once_and_persists_offset(self):
        import commands
        from contextlib import ExitStack
        confirm=self.action(self.preview(),'send')
        update=self.update(confirm);update['update_id']=55
        tg=self.root/'tg.json';tg.write_text(json.dumps({**self.cfg,'telegram_bot_token':'DUMMY'}))
        class EndLoop(Exception):pass
        connections=[];original=sqlite3.connect
        def tracked(*a,**kw):
            c=original(*a,**kw);connections.append(c);return c
        def api(token,method,args):
            if method=='getUpdates':return [update,update]
            return True
        try:
            with ExitStack() as stack:
                for obj,name,value in ((commands,'ROOT',self.root),(commands,'DB',self.root/'commands.sqlite3'),(commands,'TG',tg)):
                    stack.enter_context(patch.object(obj,name,value))
                stack.enter_context(patch.object(commands.sqlite3,'connect',side_effect=tracked))
                stack.enter_context(patch.object(commands,'api',side_effect=api))
                stack.enter_context(patch.object(commands.time,'sleep',side_effect=EndLoop))
                thread=stack.enter_context(patch.object(commands.threading,'Thread'))
                with self.assertRaises(EndLoop):commands.main()
                thread.assert_called_once()
                self.assertEqual(thread.call_args.kwargs['target'],commands._run_manual_request)
                self.assertEqual(thread.call_args.kwargs['args'][-2:],('ETHUSDT','LONG'))
                thread.return_value.start.assert_called_once()
        finally:
            for c in connections:c.close()
        with closing(sqlite3.connect(self.root/'commands.sqlite3')) as c:
            self.assertEqual(c.execute("SELECT value FROM cursor WHERE name='offset'").fetchone()[0],56)
        self.assertEqual(len(self.queued()),1)

    def test_tp_reports_never_call_order_sender_and_release_background_lock(self):
        import commands,weex_bot_tp_audit,weex_tp_repair_preflight
        for action in ('tp_check','tp_repair'):
            with patch.object(commands,'ROOT',self.root),patch.object(commands,'api') as api, \
                 patch.object(weex_bot_tp_audit,'inspect',return_value=[]) as audit, \
                 patch.object(weex_tp_repair_preflight,'preflight',return_value=[]) as preflight:
                self.assertTrue(commands._menu_report_lock.acquire(blocking=False))
                commands._run_menu_report('DUMMY','7',action)
                self.assertFalse(commands._menu_report_lock.locked())
                text=api.call_args.args[2]['text']
                if action=='tp_check':
                    audit.assert_called_once_with(self.root);preflight.assert_not_called()
                    self.assertIn('Nessun ordine inviato',text)
                else:
                    preflight.assert_called_once_with(self.root,save_proposals=True);audit.assert_not_called()
                    self.assertIn('DISABILITATO',text)


if __name__=='__main__':unittest.main()
