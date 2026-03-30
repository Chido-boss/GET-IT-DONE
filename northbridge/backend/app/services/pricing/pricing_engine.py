"""
Pricing / profit engine — estimates profit range and ROI for each investment strategy.
Numbers are illustrative ranges based on NE market norms. Always verify with professionals.
"""
from dataclasses import dataclass


@dataclass
class StrategyEstimate:
    strategy: str
    purchase_price: int
    total_cost: int
    estimated_return: int
    gross_profit: int
    roi_pct: float
    monthly_cashflow: int | None
    notes: str


# NE market assumptions (update via config in production)
NE_ASSUMPTIONS = {
    "refurb_pct": 0.08,           # 8% of purchase = light refurb
    "refurb_heavy_pct": 0.15,     # 15% = full refurb
    "selling_costs_pct": 0.025,   # agent (1%) + legal (1.5%)
    "btl_gross_yield": 0.065,     # 6.5% gross yield typical NE
    "hmo_gross_yield": 0.115,     # 11.5% HMO gross yield NE
    "hmo_costs_pct": 0.35,        # 35% of gross = bills/management/maintenance
    "mortgage_ltv": 0.75,
    "mortgage_rate": 0.055,
    "planning_cost": 15_000,      # planning consultant + application fees
    "conversion_cost_per_unit": 35_000,  # rough conversion cost per resi unit
    "stamp_duty_pct": 0.03,       # 3% additional for investment property
}


def estimate_flip(purchase_price: int, arv_override: int | None = None) -> StrategyEstimate:
    a = NE_ASSUMPTIONS
    refurb = int(purchase_price * a["refurb_pct"])
    stamp_duty = int(purchase_price * a["stamp_duty_pct"])
    selling_costs = int(purchase_price * 1.20 * a["selling_costs_pct"])  # on ARV
    arv = arv_override or int(purchase_price * 1.22)  # assume 22% uplift from refurb
    total_in = purchase_price + refurb + stamp_duty + selling_costs
    profit = arv - total_in
    roi = (profit / total_in) * 100 if total_in > 0 else 0
    return StrategyEstimate(
        strategy="Flip (Buy-Refurb-Sell)",
        purchase_price=purchase_price,
        total_cost=total_in,
        estimated_return=arv,
        gross_profit=profit,
        roi_pct=round(roi, 1),
        monthly_cashflow=None,
        notes=f"Light refurb budget £{refurb:,}. Target ARV £{arv:,}. Verify with builder quote.",
    )


def estimate_btl(purchase_price: int) -> StrategyEstimate:
    a = NE_ASSUMPTIONS
    annual_rent = int(purchase_price * a["btl_gross_yield"])
    monthly_rent = annual_rent // 12
    mortgage_balance = int(purchase_price * a["mortgage_ltv"])
    monthly_mortgage = int(mortgage_balance * a["mortgage_rate"] / 12)
    monthly_costs = int(monthly_rent * 0.18)  # mgmt + maintenance
    net_monthly = monthly_rent - monthly_mortgage - monthly_costs
    stamp_duty = int(purchase_price * a["stamp_duty_pct"])
    total_in = int(purchase_price * (1 - a["mortgage_ltv"])) + stamp_duty + 3_000  # legal
    return StrategyEstimate(
        strategy="Buy-to-Let",
        purchase_price=purchase_price,
        total_cost=total_in,
        estimated_return=annual_rent,
        gross_profit=net_monthly * 12,
        roi_pct=round((net_monthly * 12 / total_in) * 100, 1),
        monthly_cashflow=net_monthly,
        notes=f"Est. rent £{monthly_rent:,}/mo. Net cashflow £{net_monthly:,}/mo. 75% LTV @ 5.5%.",
    )


def estimate_hmo(purchase_price: int, rooms: int = 5) -> StrategyEstimate:
    a = NE_ASSUMPTIONS
    room_rent = 450  # £450/room/month typical NE
    monthly_gross = rooms * room_rent
    monthly_costs = int(monthly_gross * a["hmo_costs_pct"])
    mortgage_balance = int(purchase_price * a["mortgage_ltv"])
    monthly_mortgage = int(mortgage_balance * a["mortgage_rate"] / 12)
    net_monthly = monthly_gross - monthly_costs - monthly_mortgage
    stamp_duty = int(purchase_price * a["stamp_duty_pct"])
    total_in = int(purchase_price * (1 - a["mortgage_ltv"])) + stamp_duty + 5_000
    return StrategyEstimate(
        strategy=f"HMO ({rooms} rooms)",
        purchase_price=purchase_price,
        total_cost=total_in,
        estimated_return=monthly_gross * 12,
        gross_profit=net_monthly * 12,
        roi_pct=round((net_monthly * 12 / total_in) * 100, 1),
        monthly_cashflow=net_monthly,
        notes=f"{rooms} rooms @ £{room_rent}/mo. Gross £{monthly_gross:,}/mo. HMO licence required.",
    )


def estimate_planning_gain(purchase_price: int) -> StrategyEstimate:
    a = NE_ASSUMPTIONS
    planning_uplift = int(purchase_price * 0.35)  # 35% uplift from getting PP
    sale_price = purchase_price + planning_uplift
    costs = a["planning_cost"] + int(purchase_price * a["stamp_duty_pct"]) + 3_000
    profit = sale_price - purchase_price - costs
    total_in = purchase_price + costs
    roi = (profit / total_in) * 100 if total_in > 0 else 0
    return StrategyEstimate(
        strategy="Planning Gain",
        purchase_price=purchase_price,
        total_cost=total_in,
        estimated_return=sale_price,
        gross_profit=profit,
        roi_pct=round(roi, 1),
        monthly_cashflow=None,
        notes="Secure planning permission, sell with PP. No construction required. 12-18 month horizon.",
    )


def estimate_brrr(purchase_price: int) -> StrategyEstimate:
    """Buy-Refurb-Refinance-Rent."""
    a = NE_ASSUMPTIONS
    refurb = int(purchase_price * a["refurb_heavy_pct"])
    stamp_duty = int(purchase_price * a["stamp_duty_pct"])
    total_in = purchase_price + refurb + stamp_duty + 3_000
    refined_value = int(purchase_price * 1.28)
    refinance_amount = int(refined_value * a["mortgage_ltv"])
    cash_left_in = total_in - refinance_amount
    monthly_rent = int(refined_value * a["btl_gross_yield"] / 12)
    monthly_mortgage = int(refinance_amount * a["mortgage_rate"] / 12)
    monthly_costs = int(monthly_rent * 0.18)
    net_monthly = monthly_rent - monthly_mortgage - monthly_costs
    return StrategyEstimate(
        strategy="BRRR",
        purchase_price=purchase_price,
        total_cost=cash_left_in,
        estimated_return=int(net_monthly * 12),
        gross_profit=int(net_monthly * 12),
        roi_pct=round((net_monthly * 12 / max(cash_left_in, 1)) * 100, 1),
        monthly_cashflow=net_monthly,
        notes=f"Refinanced value £{refined_value:,}. Cash left in £{cash_left_in:,}. Recycled capital strategy.",
    )


def generate_profit_table(
    purchase_price: int,
    property_type: str,
    bedrooms: int | None,
    primary_strategy: str,
    postcode: str | None = None,
) -> list[StrategyEstimate]:
    """Generate profit estimates for viable strategies."""
    strategies = []

    if primary_strategy == "bmv_flip" or property_type in ("T", "S"):
        strategies.append(estimate_flip(purchase_price))
        strategies.append(estimate_brrr(purchase_price))

    if property_type in ("D", "S", "T"):
        strategies.append(estimate_btl(purchase_price))

    if (bedrooms or 0) >= 3 and property_type in ("T", "S", "D"):
        strategies.append(estimate_hmo(purchase_price, rooms=min(bedrooms or 5, 7)))

    if primary_strategy == "planning_gain":
        strategies.append(estimate_planning_gain(purchase_price))

    # Always include BTL as fallback
    if not strategies:
        strategies.append(estimate_btl(purchase_price))

    return strategies
