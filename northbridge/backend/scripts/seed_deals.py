"""
Northbridge Intelligence — Seed 14 realistic North East property deals.
Run from backend directory:  python scripts/seed_deals.py
"""
import asyncio, sys, os, uuid
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.models.deal import Deal
from app.database import Base
from app.services.deal_scoring import score_deal

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://northbridge:northbridge@localhost:5432/northbridge"
)

# ── 14 realistic NE deals ─────────────────────────────────────────────────────
RAW_DEALS = [

    # ── FLIP ─────────────────────────────────────────────────────────────────
    dict(
        title="3-bed terrace — distressed sale, Bensham Gateshead",
        address="14 Bensham Road, Gateshead", postcode="NE8 1AA", council="Gateshead",
        property_type="Terraced", bedrooms=3, strategy="flip",
        purchase_price=62_000, estimated_value=97_000, gdv=97_000,
        refurb_cost=18_000, other_costs=4_500,
        days_on_market=91, price_reductions=2, source="Rightmove",
        exit_strategy="Flip to owner-occupier within 4 months of acquisition",
        tags=["Distressed", "Chain Free", "High BMV", "Full Refurb"],
        summary=(
            "3-bed mid-terrace in Bensham requiring full modernisation. "
            "Asking price is 36% below comparable sales on the same street. "
            "Two price reductions in 91 days — vendor motivated and negotiable."
        ),
        risk_notes=(
            "Full refurb required; ensure structural survey prior to exchange. "
            "Street has some void properties — buyer pool may be restricted to investors."
        ),
        opportunity_notes=(
            "Comparable 3-beds on Bensham Road are consistently selling at £95-100k refurbished. "
            "Chain-free with vacant possession — can move within 4 weeks."
        ),
        description="Chain free. Vacant possession. Sold as seen. Cash buyers only. Motivated seller. Full refurbishment required.",
        status="active",
    ),

    # ── LIGHT REFURB FLIP ────────────────────────────────────────────────────
    dict(
        title="2-bed mid-terrace — light refurb flip, Dunston Gateshead",
        address="37 Ellison Road, Dunston, Gateshead", postcode="NE11 9PQ", council="Gateshead",
        property_type="Terraced", bedrooms=2, strategy="light_refurb_flip",
        purchase_price=74_000, estimated_value=104_000, gdv=104_000,
        refurb_cost=11_000, other_costs=3_800,
        days_on_market=54, price_reductions=1, source="Rightmove",
        exit_strategy="Light refurb and flip to owner-occupier in 10-12 weeks",
        tags=["Light Refurb", "Chain Free", "Quick Flip", "BMV"],
        summary=(
            "2-bed mid-terrace in established Dunston location. "
            "Cosmetic update only required — kitchens, bathrooms and decoration. "
            "Priced 28% below refurbished comparables; minimal execution risk."
        ),
        risk_notes=(
            "Area has good owner-occupier demand but limited investor pool. "
            "Ensure refurb costs are firm quotes before proceeding."
        ),
        opportunity_notes=(
            "Refurbed 2-beds in Dunston sell reliably at £100-110k. "
            "Light-touch work keeps timeline and cost risk very low."
        ),
        description="Chain free. No chain. Ready to go. Minor refurbishment only. Motivated seller.",
        status="active",
    ),

    # ── FLIP ─────────────────────────────────────────────────────────────────
    dict(
        title="4-bed semi — value-add opportunity, Fenham Newcastle",
        address="112 Fenham Hall Drive, Newcastle upon Tyne", postcode="NE4 9XB", council="Newcastle",
        property_type="Semi-Detached", bedrooms=4, strategy="flip",
        purchase_price=115_000, estimated_value=162_000, gdv=162_000,
        refurb_cost=22_000, other_costs=6_200,
        days_on_market=67, price_reductions=1, source="Rightmove",
        exit_strategy="Full refurb and sell to family buyer; 5-6 month project",
        tags=["4-Bed", "Semi-Detached", "Chain Free", "Value-Add"],
        summary=(
            "Large 4-bed semi in popular Fenham with good school catchment. "
            "Requires full modernisation but structure is sound. "
            "29% discount to comparable refurbed stock at £160-165k."
        ),
        risk_notes=(
            "Heavier refurb budget (£22k) — get fixed-price contracts before exchange. "
            "Area demand is strong but buyer pool mainly owner-occupiers, not investors."
        ),
        opportunity_notes=(
            "School catchment and park proximity drive consistent demand. "
            "Chain free with vacant possession accelerates timeline."
        ),
        description="Chain free. Vacant possession. Requires full modernisation. Large 4-bed semi.",
        status="active",
    ),

    # ── BTL ──────────────────────────────────────────────────────────────────
    dict(
        title="1-bed flat — strong yield BTL, Byker Newcastle",
        address="Flat 4, 89 Shields Road, Newcastle upon Tyne", postcode="NE6 1DL", council="Newcastle",
        property_type="Flat", bedrooms=1, strategy="btl",
        purchase_price=55_000, estimated_value=66_000, gdv=None,
        refurb_cost=3_500, other_costs=3_000,
        annual_yield=8.7, monthly_cashflow=230,
        days_on_market=38, price_reductions=0, source="Rightmove",
        exit_strategy="Hold as BTL; refinance after 12 months if yield confirmed",
        tags=["BTL", "High Yield", "Low Entry", "Near Transport"],
        summary=(
            "1-bed flat in Byker generating £475/month, equating to 8.7% gross yield on current ask. "
            "Leasehold with 88 years remaining. "
            "Located 400m from Byker Metro — strong tenant demand from young professionals."
        ),
        risk_notes=(
            "Leasehold — check service charge and ground rent before exchange. "
            "Byker is transitional; capital growth may lag compared to NE2/NE3."
        ),
        opportunity_notes=(
            "8.7% yield well above Newcastle city average of 6-7%. "
            "Tenant in situ — no void on completion."
        ),
        description="Investment property. Currently let at £475pcm. No chain. Motivated seller.",
        status="active",
    ),

    # ── BTL ──────────────────────────────────────────────────────────────────
    dict(
        title="2-bed cottage — Durham city BTL, near cathedral",
        address="5 Framwellgate, Durham", postcode="DH1 5TU", council="Durham",
        property_type="Terraced", bedrooms=2, strategy="btl",
        purchase_price=98_000, estimated_value=118_000, gdv=None,
        refurb_cost=6_000, other_costs=4_800,
        annual_yield=6.8, monthly_cashflow=200,
        days_on_market=45, price_reductions=0, source="Rightmove",
        exit_strategy="Long-term BTL hold; strong capital appreciation thesis near heritage zone",
        tags=["BTL", "Heritage Location", "Durham City", "Capital Growth"],
        summary=(
            "Attractive 2-bed terraced cottage a short walk from Durham Cathedral and university. "
            "Property rents consistently to university staff and postgraduate students. "
            "16% below estimated market value with long-term capital appreciation potential."
        ),
        risk_notes=(
            "Low cashflow (£200/month) — interest rate sensitivity is elevated. "
            "Heritage zone may restrict extension or conversion potential."
        ),
        opportunity_notes=(
            "Durham city rents have risen 12% in 24 months. "
            "University demand is year-round; void risk is minimal."
        ),
        description="Charming terraced cottage. Chain free. Investment opportunity near Durham city centre.",
        status="active",
    ),

    # ── INCOME HOLD / HMO ────────────────────────────────────────────────────
    dict(
        title="5-bed HMO — 11% gross yield, Jesmond Newcastle",
        address="19 Osborne Road, Jesmond, Newcastle upon Tyne", postcode="NE2 2AL", council="Newcastle",
        property_type="Detached", bedrooms=5, strategy="income_hold",
        purchase_price=320_000, estimated_value=340_000, gdv=None,
        refurb_cost=15_000, other_costs=12_000,
        annual_yield=11.2, monthly_cashflow=1_850,
        days_on_market=29, price_reductions=0, source="Off-market",
        exit_strategy="5-year income hold; exit via auction or block sale to HMO investor",
        tags=["HMO", "High Yield", "Student Demand", "Jesmond"],
        summary=(
            "Large Victorian detached in prime Jesmond — 5 rooms currently letting at £740/month each. "
            "11.2% gross yield; net yield approximately 8.5% after management and maintenance. "
            "Currently unlicensed — Article 4 applies; licence upgrade required."
        ),
        risk_notes=(
            "Article 4 direction applies in Jesmond — HMO licence essential. "
            "Licensing cost and management complexity elevate operational risk vs BTL."
        ),
        opportunity_notes=(
            "Jesmond commands highest HMO rents in Newcastle — rooms are consistently let within days. "
            "Off-market acquisition with motivated vendor seeking quick completion."
        ),
        description="No chain. Large Victorian detached. HMO potential. Motivated vendor. Close to Newcastle University.",
        status="active",
    ),

    # ── INCOME HOLD ──────────────────────────────────────────────────────────
    dict(
        title="4-bed licensed HMO — Walker Newcastle, strong cashflow",
        address="34 Welbeck Road, Walker, Newcastle upon Tyne", postcode="NE6 3PB", council="Newcastle",
        property_type="Terraced", bedrooms=4, strategy="income_hold",
        purchase_price=78_000, estimated_value=84_000, gdv=None,
        refurb_cost=10_000, other_costs=4_800,
        annual_yield=14.5, monthly_cashflow=920,
        days_on_market=14, price_reductions=0, source="Direct",
        exit_strategy="Income hold for 3-5 years; exit to HMO investor",
        tags=["HMO", "Licensed", "High Yield", "Low Entry"],
        summary=(
            "4-bed licensed HMO with rooms let individually at £400-430/month. "
            "14.5% gross yield — exceptional entry for an income investor. "
            "Vendor retiring from property; asking price reflects urgency."
        ),
        risk_notes=(
            "Walker is improving but remains a working-class area — tenant quality management is key. "
            "Refurb budget of £10k should be stress-tested with on-site contractor quotes."
        ),
        opportunity_notes=(
            "14.5% yield is among the highest achievable in the NE for this asset class. "
            "Licensed and operational — zero void on completion."
        ),
        description="4-bed licensed HMO. Rooms let individually. No chain. Motivated seller. Investment opportunity.",
        status="active",
    ),

    # ── FLIP ─────────────────────────────────────────────────────────────────
    dict(
        title="2-bed flat — executor sale, Sunderland city centre",
        address="22 Fawcett Street, Sunderland", postcode="SR1 1RH", council="Sunderland",
        property_type="Flat", bedrooms=2, strategy="flip",
        purchase_price=48_000, estimated_value=75_000, gdv=75_000,
        refurb_cost=14_000, other_costs=3_500,
        days_on_market=78, price_reductions=2, source="Auction",
        exit_strategy="Refurb and sell to first-time buyer or investor within 3-4 months",
        tags=["Executor Sale", "Deep BMV", "Sunderland Riverside", "High ROI"],
        summary=(
            "2-bed city-centre flat in executor sale, priced 36% below comparable refurbed units. "
            "Full modernisation required. "
            "Located within the Sunderland Riverside regeneration zone — strong future demand."
        ),
        risk_notes=(
            "Full refurb on a flat carries higher management complexity than a terrace. "
            "Check lease length, service charge and ground rent carefully before exchange."
        ),
        opportunity_notes=(
            "Sunderland Riverside development will deliver 1,000+ homes and jobs near this site. "
            "Strong ROI potential — comparables showing consistent £72-78k once refurbed."
        ),
        description="Executor sale. Chain free. In need of full modernisation. No chain. Investment opportunity.",
        status="active",
    ),

    # ── LIGHT REFURB FLIP ────────────────────────────────────────────────────
    dict(
        title="3-bed semi — Ashington Northumberland, high yield area",
        address="14 Milburn Road, Ashington, Northumberland", postcode="NE63 0RL", council="Northumberland",
        property_type="Semi-Detached", bedrooms=3, strategy="light_refurb_flip",
        purchase_price=67_000, estimated_value=94_000, gdv=94_000,
        refurb_cost=10_000, other_costs=3_200,
        days_on_market=112, price_reductions=2, source="Rightmove",
        exit_strategy="Light refurb; sell to local owner-occupier or first-time buyer",
        tags=["Northumberland", "High ROI", "BMV", "Light Refurb"],
        summary=(
            "3-bed semi in Ashington — 29% below comparable sold prices. "
            "Two price reductions in 112 days signals motivated vendor. "
            "Light cosmetic refurb only needed; strong ROI for minimal risk."
        ),
        risk_notes=(
            "Ashington is a smaller market — buyer pool mainly local; may take slightly longer to sell refurbed. "
            "Confirm heating system condition; boiler replacement may be needed."
        ),
        opportunity_notes=(
            "Comparable 3-bed semis in Ashington consistently achieve £90-95k once refurbed. "
            "Purchase price reflects sustained marketing pressure — vendor ready to deal."
        ),
        description="No chain. Needs cosmetic work. Motivated seller. Priced to sell.",
        status="active",
    ),

    # ── AUCTION ──────────────────────────────────────────────────────────────
    dict(
        title="Auction — 3-bed terrace, Hartlepool Marina",
        address="22 Grange Road, Hartlepool", postcode="TS24 8EY", council="Hartlepool",
        property_type="Terraced", bedrooms=3, strategy="auction",
        purchase_price=55_000, estimated_value=79_000, gdv=79_000,
        refurb_cost=14_000, other_costs=3_200,
        days_on_market=22, price_reductions=0, source="Auction",
        exit_strategy="Refurb and sell or hold as BTL near marina development",
        tags=["Auction", "Marina Regen", "Chain Free", "Flexible Exit"],
        summary=(
            "3-bed terrace within walking distance of the Hartlepool Marina regeneration zone. "
            "Auction guide price reflects motivated vendor and refurb requirement. "
            "30% discount to comparable refurbed stock; dual exit (flip or BTL) viable."
        ),
        risk_notes=(
            "Auction purchase — 28-day completion required; finance must be arranged in advance. "
            "Marina regeneration still ongoing; some uncertainty on timeline."
        ),
        opportunity_notes=(
            "Marina zone is delivering significant public investment in the area. "
            "BTL yields in TS24 running at 8-10% — strong fallback if flip market softens."
        ),
        description="Motivated seller. Chain free. Vacant possession. Close to marina regeneration. Requires updating.",
        status="active",
    ),

    # ── CONVERSION ───────────────────────────────────────────────────────────
    dict(
        title="Former retail unit — Class MA residential conversion, Sunderland",
        address="38 High Street West, Sunderland", postcode="SR1 3EX", council="Sunderland",
        property_type="Commercial", bedrooms=None, strategy="conversion",
        purchase_price=95_000, estimated_value=None, gdv=280_000,
        refurb_cost=120_000, other_costs=18_000,
        days_on_market=55, price_reductions=0, source="Off-market",
        exit_strategy="Convert to 4 residential units and sell individually or hold as income portfolio",
        tags=["Commercial Conversion", "Planning Uplift", "Sunderland Riverside", "High GDV"],
        summary=(
            "Former retail unit in Sunderland city centre — 1,200 sqft ground floor with Class MA prior approval route. "
            "Conversion to 3-4 residential apartments viable. GDV estimated at £280k on completion. "
            "Located in the Sunderland Riverside regeneration zone."
        ),
        risk_notes=(
            "Planning consent required — prior approval route is relatively reliable but not guaranteed. "
            "Heavy refurb budget; contractor management is the primary execution risk."
        ),
        opportunity_notes=(
            "Class MA conversions in Sunderland city centre are completing successfully. "
            "Riverside zone investment is driving apartment values — GDV may increase during construction."
        ),
        description="Former retail unit. Planning potential for change of use to residential. Ground floor 1,200 sqft. Prior approval under Class MA.",
        status="active",
    ),

    # ── BRRR ─────────────────────────────────────────────────────────────────
    dict(
        title="3-bed terrace — BRRR, Gateshead Teams",
        address="7 Dunston Road, Gateshead", postcode="NE8 4AQ", council="Gateshead",
        property_type="Terraced", bedrooms=3, strategy="brrr",
        purchase_price=72_000, estimated_value=115_000, gdv=115_000,
        refurb_cost=20_000, other_costs=5_000,
        days_on_market=43, price_reductions=1, source="Rightmove",
        exit_strategy="Refurb, refinance at post-works valuation, hold as BTL",
        tags=["BRRR", "Refinance Play", "Gateshead", "High BMV"],
        summary=(
            "3-bed terrace in Teams, Gateshead — 37% below estimated post-works value. "
            "Strong BRRR candidate: refurb to a £115k valuation, then refinance at 75% LTV and recover most capital. "
            "Rental demand strong in this area — expected £650-700/month."
        ),
        risk_notes=(
            "Refinance valuation is the hinge point — confirm with local surveyor before exchange. "
            "Teams is an improving area but stigma may cap valuations; use conservative ARV."
        ),
        opportunity_notes=(
            "Post-works refinance at 75% LTV would return approximately £86k — most of the capital deployed. "
            "Rental yield on retained equity will be exceptional."
        ),
        description="Cash buyers only. Motivated seller seeking quick sale. Chain free. Requires updating throughout.",
        status="active",
    ),

    # ── LIGHT REFURB FLIP ────────────────────────────────────────────────────
    dict(
        title="2-bed terrace — Blyth Estuary zone, Northumberland",
        address="16 Renwick Road, Blyth, Northumberland", postcode="NE24 2RR", council="Northumberland",
        property_type="Terraced", bedrooms=2, strategy="light_refurb_flip",
        purchase_price=58_000, estimated_value=82_000, gdv=82_000,
        refurb_cost=9_000, other_costs=3_000,
        days_on_market=88, price_reductions=1, source="Rightmove",
        exit_strategy="Light refurb and sell to first-time buyer or young professional",
        tags=["Blyth Estuary", "Regen Zone", "Light Refurb", "High ROI"],
        summary=(
            "2-bed terrace in Blyth — within the Blyth Estuary regeneration zone. "
            "29% below comparable refurbed sales. Light cosmetic work only. "
            "Regeneration investment in Blyth port area is beginning to pull prices up."
        ),
        risk_notes=(
            "Blyth has historically low prices — buyer pool is narrower than in Newcastle or Gateshead. "
            "Confirm rental demand data if considering BTL fallback."
        ),
        opportunity_notes=(
            "Blyth Estuary zone is receiving significant investment; early movers are seeing rapid appreciation. "
            "Light refurb with 29% entry discount gives a strong margin of safety."
        ),
        description="No chain. Cosmetic work required. Investment opportunity near Blyth regeneration zone.",
        status="active",
    ),

    # ── INCOME HOLD ──────────────────────────────────────────────────────────
    dict(
        title="4-bed HMO — Sunderland University quarter, licensed",
        address="88 Toward Road, Sunderland", postcode="SR2 7EH", council="Sunderland",
        property_type="Terraced", bedrooms=4, strategy="income_hold",
        purchase_price=88_000, estimated_value=96_000, gdv=None,
        refurb_cost=8_000, other_costs=5_000,
        annual_yield=13.8, monthly_cashflow=780,
        days_on_market=31, price_reductions=0, source="Direct",
        exit_strategy="Hold for income; exit via sale to HMO investor after 3 years",
        tags=["HMO", "Licensed", "Student Quarter", "High Yield"],
        summary=(
            "4-room licensed HMO in the Sunderland University student quarter. "
            "4 rooms letting at £450/month gross income £1,800/month. "
            "13.8% gross yield — 8% below comparable HMO asking prices."
        ),
        risk_notes=(
            "Student demand is seasonal — ensure ASTs have summer holding provisions. "
            "Sunderland University intake is stable but smaller than Newcastle; monitor for changes."
        ),
        opportunity_notes=(
            "13.8% gross yield is exceptional even by NE HMO standards. "
            "Licensed asset reduces regulatory risk and makes future resale straightforward."
        ),
        description="Licensed HMO. 4 rooms let at £450/room. Gross income £1,800pcm. No chain. Investment opportunity.",
        status="active",
    ),
]


async def seed():
    engine = create_async_engine(DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # Clear existing deals
        from sqlalchemy import text
        await session.execute(text("DELETE FROM deals"))
        await session.commit()

        print("Seeding 14 NE deals with full scoring...\n")
        count = 0
        for raw in RAW_DEALS:
            s = score_deal(
                purchase_price=raw["purchase_price"],
                strategy=raw["strategy"],
                estimated_value=raw.get("estimated_value"),
                gdv=raw.get("gdv"),
                refurb_cost=raw.get("refurb_cost", 0),
                other_costs=raw.get("other_costs", 0),
                description=raw.get("description", ""),
                postcode=raw.get("postcode", ""),
                bedrooms=raw.get("bedrooms"),
                days_on_market=raw.get("days_on_market"),
                price_reductions=raw.get("price_reductions"),
                annual_yield_pct=raw.get("annual_yield"),
            )

            exit_value = raw.get("gdv") or raw.get("estimated_value")
            gross_profit = (exit_value - raw["purchase_price"]) if exit_value else None

            deal = Deal(
                id=uuid.uuid4(),
                title=raw["title"],
                address=raw["address"],
                postcode=raw.get("postcode"),
                council=raw.get("council"),
                property_type=raw.get("property_type"),
                bedrooms=raw.get("bedrooms"),
                strategy=raw["strategy"],
                exit_strategy=raw.get("exit_strategy"),
                source=raw.get("source"),
                days_on_market=raw.get("days_on_market"),
                price_reductions=raw.get("price_reductions"),
                # Financials
                purchase_price=raw["purchase_price"],
                asking_price=raw["purchase_price"],
                estimated_value=raw.get("estimated_value"),
                gdv=raw.get("gdv"),
                refurb_cost=raw.get("refurb_cost"),
                other_costs=raw.get("other_costs"),
                total_cost=s.total_cost,
                gross_profit=gross_profit,
                profit=s.net_profit,
                net_profit=s.net_profit,
                roi=s.roi_pct,
                roi_pct=s.roi_pct,
                discount_pct=s.discount_pct,
                annual_yield=raw.get("annual_yield"),
                annual_yield_pct=raw.get("annual_yield"),
                monthly_cashflow=raw.get("monthly_cashflow"),
                # Intelligence flags
                is_undervalued=s.is_undervalued,
                has_planning_upside=s.has_planning_upside,
                is_high_roi=s.is_high_roi,
                is_distressed=s.is_distressed,
                near_regen_zone=s.near_regen_zone,
                # Component scores
                score_roi=s.score_roi,
                score_discount=s.score_discount,
                score_risk=s.score_risk,
                score_liquidity=s.score_liquidity,
                # Overall
                overall_score=s.overall_score,
                tier=s.tier,
                confidence=s.confidence,
                risk_level=s.risk_level,
                # Legacy scores
                roi_score=s.roi_score,
                risk_score=s.risk_score,
                planning_uplift_score=s.planning_uplift_score,
                market_score=s.market_score,
                score_drivers=s.score_drivers,
                # Context
                tags=raw.get("tags", []),
                summary=raw.get("summary"),
                risk_notes=raw.get("risk_notes"),
                opportunity_notes=raw.get("opportunity_notes"),
                description=raw.get("description"),
                status=raw.get("status", "active"),
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            session.add(deal)
            count += 1

            roi_str = f"{s.roi_pct:.0f}% ROI" if s.roi_pct else (
                f"{raw.get('annual_yield', 0):.1f}% yield" if raw.get("annual_yield") else "—"
            )
            print(
                f"  [{s.tier}] {s.overall_score:5.1f}  {raw['title'][:55]:<55}  {roi_str}"
            )

        await session.commit()
        print(f"\n✓ {count} deals seeded and scored")
        print("\nScore distribution:")
        for tier in ["S", "A", "B", "C"]:
            deals_in_tier = [d for d in RAW_DEALS if True]  # placeholder
        print("  Run the app and check /deals to see the ranked pipeline.")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
