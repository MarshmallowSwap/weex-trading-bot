"""WEEX break-even resolver. Pure calculations only; no API keys or orders."""
from decimal import Decimal
from dataclasses import dataclass
D=lambda x: Decimal(str(x))
@dataclass(frozen=True)
class BreakEven:
    price: Decimal
    source: str
    reason: str

def resolve(position, *, closing_taker_rate, expected_slippage_rate=0, extra_cost_usdt=0):
    """Linear USDT position; fees in USDT. Price provided directly by exchange is preferred
    only when declared inclusive of exit costs by adapter; otherwise calculate conservatively."""
    side=str(position["side"]).upper()
    if side not in ("LONG","SHORT"): raise ValueError("Unsupported side")
    qty=D(position["base_quantity"])
    entry=D(position["avg_entry_price"])
    if qty<=0 or entry<=0:raise ValueError("Invalid quantity/entry")
    direction=D(1) if side=="LONG" else D(-1)
    fee=D(closing_taker_rate)
    slip=D(expected_slippage_rate)
    if fee<0 or fee>=D("0.1") or slip<0 or slip>=D("0.1"):raise ValueError("Invalid fee/slippage")
    provided=position.get("exchange_break_even_price")
    if provided is not None and position.get("exchange_be_includes_exit_costs") is True:
        candidate=D(provided)
        if candidate>0:
            return BreakEven(candidate,"exchange","Exchange break-even verified by adapter as including expected exit fees")
    opening=D(position.get("allocated_open_fee_usdt",0))
    funding=D(position.get("net_funding_paid_usdt",0))
    other=D(extra_cost_usdt)
    if min(opening,other)<0:raise ValueError("Negative cost")
    # Sign-convention: positive funding = paid; negative funding = received.
    # LONG: qty*(P-entry) - qty*P*(fee+slip) - costs = 0
    # SHORT: qty*(entry-P) - qty*P*(fee+slip) - costs = 0
    costs=opening+funding+other
    denom=qty*(direction-(fee+slip))
    if denom==0:raise ValueError("Zero denominator")
    be=(qty*direction*entry+costs)/denom
    if be<=0:raise ValueError("Invalid break-even")
    return BreakEven(be,"calculated","Includes allocated open fees, signed funding, estimated exit fee and slippage")

def target_price(position, be:BreakEven, net_target_usdt, *, closing_taker_rate=0, expected_slippage_rate=0):
    """Return theoretical limit trigger price, before tick rounding and fill variance."""
    qty=D(position["base_quantity"])
    side=str(position["side"]).upper()
    direction=D(1) if side=="LONG" else D(-1) if side=="SHORT" else None
    if direction is None or qty<=0:raise ValueError("Bad position")
    target=D(net_target_usdt)
    if target<=0:raise ValueError("Target must be positive")
    # Extra PnL beyond BE loses/gains exit fee according to changed exit price.
    rate=D(closing_taker_rate)+D(expected_slippage_rate)
    denom=qty*(direction-rate)
    if (denom>0)!=(direction>0):raise ValueError("Unsafe denominator")
    price=be.price+target/denom
    if price<=0:raise ValueError("Invalid target price")
    return price
