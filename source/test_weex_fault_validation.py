"""Adversarial exchange fixtures. Every order exists only in local memory."""
import copy,json,tempfile,unittest
from pathlib import Path
from decimal import Decimal
from unittest.mock import patch
from weex_lifecycle import Lifecycle
from test_weex_lifecycle import Exchange,CFG,PLAN
import test_weex_lifecycle as fixtures

class FaultValidation(unittest.TestCase):
    setUp=fixtures.LifecycleTests.setUp
    ctx=fixtures.LifecycleTests.ctx
    entry=fixtures.LifecycleTests.entry
    def test_entry_ack_and_observed_order_id_must_agree(self):
        original=self.exchange.write
        def write(op,p):
            ack=original(op,p)
            return {**ack,'orderId':'999'} if op=='post_capi_v3_order' else ack
        with patch.object(self.exchange,'write',side_effect=write):result=self.entry()
        self.assertEqual(result['state'],'REVIEW_REQUIRED')
        self.assertEqual(len(self.exchange.calls),1)
    def test_entry_cost_or_fee_revision_does_not_certify_old_tp(self):
        self.entry()
        for field,value in [('price','2510'),('commission','0.08')]:
            original=self.exchange.trades[0][field];self.exchange.trades[0][field]=value
            self.assertEqual(self.engine.reconcile(self.tid)['state'],'REVIEW_REQUIRED')
            self.exchange.trades[0][field]=original
        self.assertEqual(len(self.exchange.calls),2)
    def test_position_side_change_cannot_remain_protected(self):
        self.entry();self.exchange.positions[0]['side']='SHORT'
        self.assertEqual(self.engine.reconcile(self.tid)['state'],'REVIEW_REQUIRED')
    def test_conflicting_open_and_history_tp_payloads_are_rejected(self):
        self.entry();original=self.exchange.read
        def read(op,**q):
            data=original(op,**q)
            if op=='get_capi_v3_allAlgoOrders':data['orders'][0]['quantity']='99'
            return data
        with patch.object(self.exchange,'read',side_effect=read):
            self.assertEqual(self.engine.reconcile(self.tid)['state'],'REVIEW_REQUIRED')
    def test_network_failure_after_entry_recovers_without_duplicate(self):
        original=self.exchange.read;failed=[False]
        def read(op,**q):
            if op=='get_capi_v3_userTrades' and not failed[0]:failed[0]=True;raise TimeoutError()
            return original(op,**q)
        with patch.object(self.exchange,'read',side_effect=read):
            self.assertEqual(self.entry()['state'],'RECONCILIATION_PENDING')
            restarted=Lifecycle(self.path,self.exchange,lambda:self.cfg)
            self.assertEqual(restarted.advance(self.tid,self.ctx)['state'],'TP_PENDING')
            self.assertEqual(restarted.reconcile(self.tid)['state'],'PROTECTED')
        self.assertEqual(len(self.exchange.calls),2)
    def test_process_crash_after_exchange_acceptance_recovers_exact_entry(self):
        original=self.exchange.write
        def crash(op,p):
            ack=original(op,p)
            if op=='post_capi_v3_order':raise KeyboardInterrupt()
            return ack
        with patch.object(self.exchange,'write',side_effect=crash),self.assertRaises(KeyboardInterrupt):self.entry()
        restarted=Lifecycle(self.path,self.exchange,lambda:self.cfg)
        self.assertEqual(restarted.advance(self.tid,self.ctx)['state'],'TP_PENDING')
        self.assertEqual(restarted.reconcile(self.tid)['state'],'PROTECTED')
        self.assertEqual(sum(op=='post_capi_v3_order' for op,p in self.exchange.calls),1)
    def test_tp_rejection_stays_unprotected_and_is_never_resent(self):
        original=self.exchange.write
        def write(op,p):
            if op=='post_capi_v3_placeTpSlOrder':
                self.exchange.calls.append((op,copy.deepcopy(p)));return [{'success':False,'errorCode':'REJECTED'}]
            return original(op,p)
        with patch.object(self.exchange,'write',side_effect=write):
            self.assertEqual(self.entry()['state'],'REVIEW_REQUIRED')
            self.assertEqual(self.engine.reconcile(self.tid)['state'],'REVIEW_REQUIRED')
        self.assertEqual(len(self.exchange.calls),2)
    def test_partial_exit_is_not_closed_and_does_not_close_manual_residual(self):
        self.entry();self.exchange.algos[0].update(algoStatus='TRIGGERED',actualOrderId='3')
        self.exchange.positions[0]['size']='0.005'
        self.assertEqual(self.engine.reconcile(self.tid)['state'],'REVIEW_REQUIRED')
        self.assertEqual(len(self.exchange.calls),2)
    def test_wrong_exit_order_id_is_not_a_closure(self):
        self.entry();self.exchange.positions=[];self.exchange.algos[0].update(algoStatus='FILLED',actualOrderId='3')
        original=self.exchange.read
        def read(op,**q):
            data=original(op,**q)
            if op=='get_capi_v3_order' and str(q.get('orderId'))=='3':data['orderId']='999'
            return data
        with patch.object(self.exchange,'read',side_effect=read):self.assertEqual(self.engine.reconcile(self.tid)['state'],'REVIEW_REQUIRED')
    def test_close_persists_actual_net_pnl_excluding_funding(self):
        self.entry();self.exchange.positions=[];self.exchange.algos[0].update(algoStatus='FILLED',actualOrderId='3')
        result=self.engine.reconcile(self.tid)
        self.assertEqual(result['state'],'CLOSED')
        own=result['owned'];expected=Decimal(own['quantity'])*Decimal(own['tpRequest']['triggerPrice'])-Decimal(own['actualEntryCostUSDT'])-Decimal(own['actualEntryFeesUSDT'])-Decimal('0.04')
        self.assertEqual(Decimal(result['detail']['realizedNetBeforeFundingUSDT']),expected)
        self.assertFalse(result['detail']['fundingIncluded'])
    def test_close_with_worse_execution_does_not_claim_profit_target(self):
        self.entry();self.exchange.positions=[];self.exchange.algos[0].update(algoStatus='FILLED',actualOrderId='3')
        original=self.exchange.read
        def read(op,**q):
            data=original(op,**q)
            if op=='get_capi_v3_userTrades' and str(q.get('orderId'))=='3':data[0]['price']='2490'
            return data
        with patch.object(self.exchange,'read',side_effect=read):result=self.engine.reconcile(self.tid)
        self.assertEqual(result['state'],'CLOSED')
        self.assertFalse(result['detail']['targetMetBeforeFunding'])
        self.assertLess(Decimal(result['detail']['realizedNetBeforeFundingUSDT']),0)
    def test_short_entry_tp_and_close_with_realized_profit(self):
        plan=copy.deepcopy(PLAN);plan['orderPreview'].update(side='SELL',positionSide='SHORT')
        tid=self.engine.prepare('short-fault-test',plan)['id']
        self.engine.advance(tid,lambda s:{**self.ctx(s),'marketSignal':'SHORT'})
        self.exchange.positions=[];self.exchange.algos[0].update(algoStatus='FILLED',actualOrderId='3')
        original=self.exchange.read
        def read(op,**q):
            data=original(op,**q)
            if str(q.get('orderId'))=='3':
                for row in data if isinstance(data,list) else [data]:row.update(positionSide='SHORT',side='BUY')
            return data
        with patch.object(self.exchange,'read',side_effect=read):result=self.engine.reconcile(tid)
        self.assertEqual(result['state'],'CLOSED')
        self.assertGreater(Decimal(result['detail']['realizedNetBeforeFundingUSDT']),0)
    def test_crash_after_tp_acceptance_is_recovered_without_duplicate_tp(self):
        original=self.exchange.write
        def crash(op,p):
            ack=original(op,p)
            if op=='post_capi_v3_placeTpSlOrder':raise KeyboardInterrupt()
            return ack
        with patch.object(self.exchange,'write',side_effect=crash),self.assertRaises(KeyboardInterrupt):self.entry()
        restarted=Lifecycle(self.path,self.exchange,lambda:self.cfg)
        self.assertEqual(restarted.reconcile(self.tid)['state'],'PROTECTED')
        self.assertEqual(len(self.exchange.calls),2)

if __name__=='__main__':unittest.main()
