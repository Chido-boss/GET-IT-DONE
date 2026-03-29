"""
Deal scoring engine — evaluates properties and opportunities across multiple strategies.
"""
import aiosqlite
import os
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)
DB_FILE = os.getenv("DB_FILE", "northbridge.db")

@dataclass
class DealScore:
    address: str
    asking_price: int
    estimated_value: int
    discount_pct: float
    bmv_score: float
    strategies: list[str]
    flags: list[str]
    verdict: str

BMV_INDICATORS = [
    "chain free", "no chain", "vacant possession", "sold as seen",
    "motivated seller", "quick sale", "offers invited", "reduced",
    "price reduction", "repossession", "executor", "probate",
    "investment opportunity", "development opportunity", "refurbishment",
    "potential", "requires updating", "in need of modernisation",
    "cash buyer", "as seen", "ground rent", "auction",
]

CONVERSION_INDICATORS = [
    "commercial", "office", "retail", "shop", "warehouse", "barn",
    "agricultural", "former", "mixed use", "investment",
]

def score_listing(listing: dict, comparables: dict) -> DealScore:
    """Score a property listing against market comparables."""
    asking = listing.get("asking_price", 0)
    description = (listing.get("description", "") or "").lower()
    prop_type = listing.get("property_type", "")
    flags = []
    strategies = []

    # BMV scoring
    bmv_score = 0.0
    discount_pct = 0.0

    if comparables.get("avg") and asking > 0:
        avg = comparables["avg"]
        if asking < avg:
            discount_pct = ((avg - asking) / avg) * 100
            if discount_pct >= 20:
                bmv_score += 50
                flags.append(f"🔥 {discount_pct:.0f}% below market avg (£{avg:,})")
                strategies.append("BMV Flip")
                strategies.append("BTL / HMO")
            elif discount_pct >= 10:
                bmv_score += 30
                flags.append(f"📉 {discount_pct:.0f}% below market avg (£{avg:,})")
                strategies.append("BMV")
            elif discount_pct >= 5:
                bmv_score += 15
                flags.append(f"Below average by {discount_pct:.0f}%")

    # Motivated seller indicators
    indicator_hits = [kw for kw in BMV_INDICATORS if kw in description]
    if indicator_hits:
        bmv_score += len(indicator_hits) * 5
        flags.append(f"Seller indicators: {', '.join(indicator_hits[:3])}")

    # Conversion / arbitrage opportunity
    if any(kw in description for kw in CONVERSION_INDICATORS):
        bmv_score += 20
        strategies.append("Conversion / Arbitrage")
        flags.append("Possible conversion play (commercial→resi)")

    # Days on market
    dom = listing.get("days_on_market", 0)
    if dom and dom > 90:
        bmv_score += 15
        flags.append(f"On market {dom} days — motivated seller likely")
    elif dom and dom > 60:
        bmv_score += 8
        flags.append(f"On market {dom} days")

    # Long days + price reduction = strong signal
    if dom and dom > 60 and discount_pct > 10:
        strategies.append("Negotiation Play")
        flags.append("Long DOM + below asking = negotiation leverage")

    bmv_score = min(bmv_score, 100.0)

    if bmv_score >= 70:
        verdict = "STRONG OPPORTUNITY"
    elif bmv_score >= 45:
        verdict = "WORTH INVESTIGATING"
    elif bmv_score >= 20:
        verdict = "MONITOR"
    else:
        verdict = "PASS"

    if not strategies:
        strategies = ["Standard Purchase"]

    return DealScore(
        address=listing.get("address", ""),
        asking_price=asking,
        estimated_value=comparables.get("avg") or asking,
        discount_pct=discount_pct,
        bmv_score=bmv_score,
        strategies=strategies,
        flags=flags,
        verdict=verdict,
    )


def calculate_deal_metrics(purchase_price: int, strategy: str, **kwargs) -> dict:
    """
    Calculate financial metrics for a given strategy.
    strategies: flip, btl, hmo, planning_gain, conversion
    """
    if strategy == "flip":
        refurb = kwargs.get("refurb_cost", int(purchase_price * 0.10))
        selling_costs = int(purchase_price * 0.03)  # legal + agent
        arv = kwargs.get("arv", int(purchase_price * 1.25))  # after repair value
        profit = arv - purchase_price - refurb - selling_costs
        roi = (profit / (purchase_price + refurb)) * 100
        return {
            "strategy": "Flip",
            "purchase_price": purchase_price,
            "refurb_cost": refurb,
            "selling_costs": selling_costs,
            "arv": arv,
            "gross_profit": profit,
            "roi_pct": round(roi, 1),
            "notes": f"Target ARV: £{arv:,}. Needs refurb budget: £{refurb:,}"
        }

    elif strategy == "btl":
        monthly_rent = kwargs.get("monthly_rent", int(purchase_price * 0.004))  # 0.4% rule
        annual_rent = monthly_rent * 12
        gross_yield = (annual_rent / purchase_price) * 100
        mortgage_payment = int(purchase_price * 0.75 * 0.055 / 12)  # 75% LTV, 5.5% rate
        net_monthly = monthly_rent - mortgage_payment - int(monthly_rent * 0.2)  # 20% costs
        return {
            "strategy": "Buy-to-Let",
            "purchase_price": purchase_price,
            "monthly_rent": monthly_rent,
            "annual_rent": annual_rent,
            "gross_yield_pct": round(gross_yield, 2),
            "mortgage_payment": mortgage_payment,
            "net_monthly_cashflow": net_monthly,
            "notes": f"Gross yield: {gross_yield:.1f}%. Target 6%+ for NE market."
        }

    elif strategy == "hmo":
        rooms = kwargs.get("rooms", 5)
        room_rent = kwargs.get("room_rent", 450)
        monthly_gross = rooms * room_rent
        annual_gross = monthly_gross * 12
        gross_yield = (annual_gross / purchase_price) * 100
        # HMO costs higher — bills, management, maintenance
        costs_monthly = int(monthly_gross * 0.35)
        net_monthly = monthly_gross - costs_monthly
        return {
            "strategy": "HMO",
            "purchase_price": purchase_price,
            "rooms": rooms,
            "room_rent": room_rent,
            "monthly_gross": monthly_gross,
            "annual_gross": annual_gross,
            "gross_yield_pct": round(gross_yield, 2),
            "costs_monthly": costs_monthly,
            "net_monthly_cashflow": net_monthly,
            "notes": f"{rooms} rooms @ £{room_rent}/mo. NE HMO demand strong near universities."
        }

    elif strategy == "planning_gain":
        planning_cost = kwargs.get("planning_cost", 15000)  # planning app + consultant
        uplift_value = kwargs.get("uplift_value", int(purchase_price * 0.40))
        profit = uplift_value - planning_cost
        roi = (profit / (purchase_price + planning_cost)) * 100
        return {
            "strategy": "Planning Gain",
            "purchase_price": purchase_price,
            "planning_cost": planning_cost,
            "value_uplift": uplift_value,
            "gross_profit": profit,
            "roi_pct": round(roi, 1),
            "notes": "Secure planning permission, sell with planning in place. No build required."
        }

    elif strategy == "conversion":
        conversion_cost = kwargs.get("conversion_cost", int(purchase_price * 0.30))
        units = kwargs.get("units", 4)
        gdv = kwargs.get("gdv", int(purchase_price * 1.8))  # gross development value
        dev_costs = conversion_cost + int(purchase_price * 0.05)  # plus fees/finance
        profit = gdv - purchase_price - dev_costs
        roi = (profit / (purchase_price + dev_costs)) * 100
        return {
            "strategy": "Commercial to Residential Conversion",
            "purchase_price": purchase_price,
            "conversion_cost": conversion_cost,
            "units": units,
            "gdv": gdv,
            "total_cost": purchase_price + dev_costs,
            "gross_profit": profit,
            "roi_pct": round(roi, 1),
            "notes": f"{units} residential units. GDV: £{gdv:,}. PD rights may apply."
        }

    return {"strategy": strategy, "purchase_price": purchase_price, "notes": "Unknown strategy"}


async def get_top_opportunities(limit: int = 20) -> list[dict]:
    """Return top-scored properties from the database."""
    async with aiosqlite.connect(DB_FILE) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT * FROM properties
               WHERE status = 'active' AND bmv_score IS NOT NULL
               ORDER BY bmv_score DESC LIMIT ?""",
            (limit,)
        )
        return [dict(r) for r in await cursor.fetchall()]
