"""
Seed 18 realistic North East property deals with full financials.
Run: python scripts/seed_deals.py
"""
import asyncio, sys, os, uuid
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.models.deal import Deal
from app.database import Base
from app.services.deal_scoring import score_deal

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://northbridge:northbridge@localhost:5432/northbridge")

RAW_DEALS = [
    # FLIPS ──────────────────────────────────────────────────────────────────
    dict(
        title="3-bed terraced flip, Bensham Gateshead",
        address="14 Bensham Road, Gateshead", postcode="NE8 1AA", council="Gateshead",
        property_type="Terraced", bedrooms=3, strategy="flip",
        purchase_price=62_000, estimated_value=97_000, gdv=97_000,
        refurb_cost=18_000, other_costs=4_500,
        description="Chain free. Vacant possession. Sold as seen. Cash buyers only. Motivated seller. Full refurbishment required.",
        status="active",
    ),
    dict(
        title="2-bed flat conversion, Sunderland city centre",
        address="22 Fawcett Street, Sunderland", postcode="SR1 1RH", council="Sunderland",
        property_type="Flat", bedrooms=2, strategy="flip",
        purchase_price=48_000, estimated_value=75_000, gdv=75_000,
        refurb_cost=14_000, other_costs=3_800,
        description="Executor sale. Chain free. In need of full modernisation. No chain. Investment opportunity.",
        status="active",
    ),
    dict(
        title="4-bed semi, potential 5-bed, Fenham Newcastle",
        address="112 Fenham Hall Drive, Newcastle", postcode="NE4 9XB", council="Newcastle",
        property_type="Semi-Detached", bedrooms=4, strategy="flip",
        purchase_price=115_000, estimated_value=162_000, gdv=162_000,
        refurb_cost=22_000, other_costs=6_200,
        description="Chain free. Vacant possession. Requires full modernisation. Large 4-bed semi.",
        status="active",
    ),

    # BRR/BRRR ───────────────────────────────────────────────────────────────
    dict(
        title="3-bed terrace BRRR, Teams Gateshead",
        address="7 Dunston Road, Gateshead", postcode="NE8 4AQ", council="Gateshead",
        property_type="Terraced", bedrooms=3, strategy="brrr",
        purchase_price=72_000, estimated_value=115_000, gdv=115_000,
        refurb_cost=20_000, other_costs=5_000,
        description="Cash buyers only. Motivated seller seeking quick sale. Chain free. Requires updating throughout.",
        status="active",
    ),
    dict(
        title="2-bed terrace BRRR, Stockton-on-Tees",
        address="18 Norton Road, Stockton-on-Tees", postcode="TS18 2AB", council="Stockton",
        property_type="Terraced", bedrooms=2, strategy="brrr",
        purchase_price=54_000, estimated_value=82_000, gdv=82_000,
        refurb_cost=14_000, other_costs=3_500,
        description="Investment property. No chain. Priced to sell. Refurbishment opportunity.",
        status="active",
    ),

    # HMO ────────────────────────────────────────────────────────────────────
    dict(
        title="5-bed HMO near Newcastle University",
        address="19 Osborne Road, Jesmond, Newcastle", postcode="NE2 2AL", council="Newcastle",
        property_type="Detached", bedrooms=5, strategy="hmo",
        purchase_price=320_000, estimated_value=320_000, gdv=None,
        refurb_cost=15_000, other_costs=12_000,
        annual_yield=11.2, monthly_cashflow=1_850,
        description="No chain. Large Victorian detached. HMO potential — 7-8 rooms possible. Motivated vendor. Close to Newcastle University and Northumbria University.",
        status="active",
    ),
    dict(
        title="4-bed HMO, Sunderland University quarter",
        address="88 Toward Road, Sunderland", postcode="SR2 7EH", council="Sunderland",
        property_type="Terraced", bedrooms=4, strategy="hmo",
        purchase_price=88_000, estimated_value=88_000, gdv=None,
        refurb_cost=8_000, other_costs=5_000,
        annual_yield=13.8, monthly_cashflow=780,
        description="Licensed HMO. 4 rooms let at £450/room. Gross income £1,800pcm. No chain. Investment opportunity.",
        status="active",
    ),

    # BTL ────────────────────────────────────────────────────────────────────
    dict(
        title="1-bed investment flat, Byker Newcastle",
        address="Flat 2, 89 Shields Road, Newcastle", postcode="NE6 1DL", council="Newcastle",
        property_type="Flat", bedrooms=1, strategy="btl",
        purchase_price=55_000, estimated_value=62_000, gdv=None,
        refurb_cost=3_000, other_costs=3_200,
        annual_yield=8.7, monthly_cashflow=220,
        description="Investment property. Currently let at £475pcm. No chain. Motivated seller.",
        status="active",
    ),
    dict(
        title="2-bed cottage, Durham city centre BTL",
        address="5 Framwellgate, Durham", postcode="DH1 5TU", council="Durham",
        property_type="Terraced", bedrooms=2, strategy="btl",
        purchase_price=98_000, estimated_value=115_000, gdv=None,
        refurb_cost=6_000, other_costs=4_800,
        annual_yield=6.8, monthly_cashflow=195,
        description="Charming terraced cottage. Chain free. Investment opportunity near Durham city centre.",
        status="active",
    ),

    # CONVERSION / PLANNING UPLIFT ───────────────────────────────────────────
    dict(
        title="Former retail unit — residential conversion, SR1",
        address="38 High Street West, Sunderland", postcode="SR1 3EX", council="Sunderland",
        property_type="Commercial", bedrooms=None, strategy="conversion",
        purchase_price=95_000, estimated_value=None, gdv=280_000,
        refurb_cost=120_000, other_costs=18_000,
        description="Former retail unit. Planning potential for change of use to residential. Ground floor 1,200 sqft. Prior approval under Class MA. Commercial to residential conversion. Cash buyers only.",
        status="active",
    ),
    dict(
        title="Former pub — 4-unit residential conversion, Winlaton",
        address="The Crown Inn, Front Street, Winlaton", postcode="NE21 4EB", council="Gateshead",
        property_type="Commercial", bedrooms=None, strategy="conversion",
        purchase_price=125_000, estimated_value=None, gdv=380_000,
        refurb_cost=160_000, other_costs=22_000,
        description="Former pub — vacant. Ideal for residential conversion. Prior approval potential. Change of use. Development opportunity. Cash buyers only. Planning uplift opportunity.",
        status="active",
    ),
    dict(
        title="Office building — Class MA conversion, Grey Street NE1",
        address="12 Grey Street, Newcastle upon Tyne", postcode="NE1 6AE", council="Newcastle",
        property_type="Commercial", bedrooms=None, strategy="conversion",
        purchase_price=375_000, estimated_value=None, gdv=820_000,
        refurb_cost=280_000, other_costs=42_000,
        description="Grade II listed office building. Potential for conversion to residential (Class MA). City centre location. Motivated vendor. Planning uplift potential. Prior approval route viable.",
        status="active",
    ),

    # PLANNING UPLIFT ────────────────────────────────────────────────────────
    dict(
        title="Agricultural barn — planning uplift, Ponteland",
        address="Highfield Farm, Ponteland Road, Northumberland", postcode="NE20 9BP",
        council="Northumberland", property_type="Land/Agricultural", bedrooms=None,
        strategy="planning_uplift",
        purchase_price=210_000, estimated_value=None, gdv=650_000,
        refurb_cost=180_000, other_costs=28_000,
        description="Redundant agricultural buildings with planning potential. Agricultural to residential conversion. Barn conversion. Outline planning being sought. Rural setting. Planning uplift.",
        status="active",
    ),
    dict(
        title="Land with planning potential, Teesworks fringe",
        address="Former Warehouse Site, Kirkleatham Lane, Redcar", postcode="TS10 5RY",
        council="Redcar & Cleveland", property_type="Land/Industrial", bedrooms=None,
        strategy="planning_uplift",
        purchase_price=185_000, estimated_value=None, gdv=520_000,
        refurb_cost=80_000, other_costs=24_000,
        description="Industrial unit 3,500 sqft adjacent to Teesworks freeport zone. Motivated seller. Planning potential for logistics, manufacturing or residential conversion. Cash buyers.",
        status="active",
    ),

    # AUCTION ────────────────────────────────────────────────────────────────
    dict(
        title="Auction lot — 3-bed terrace, Middlesbrough",
        address="67 Linthorpe Road, Middlesbrough", postcode="TS1 3QQ", council="Middlesbrough",
        property_type="Semi-Detached", bedrooms=3, strategy="auction",
        purchase_price=68_000, estimated_value=92_000, gdv=92_000,
        refurb_cost=16_000, other_costs=3_800,
        description="Auction lot. Chain free. Vacant possession. Cash buyers only. Sold as seen. Refurbishment required. Guide price £68,000.",
        status="active",
    ),
    dict(
        title="Auction — waterfront flat, South Shields",
        address="Flat 1, 3 Ocean Road, South Shields", postcode="NE33 2JA",
        council="South Tyneside", property_type="Flat", bedrooms=1, strategy="auction",
        purchase_price=42_000, estimated_value=68_000, gdv=68_000,
        refurb_cost=12_000, other_costs=2_800,
        description="Auction. Chain free. Probate sale. In need of full refurbishment. Cash buyers only. Investment opportunity near seafront. Guide price £42,000.",
        status="active",
    ),
    dict(
        title="Auction — 3-bed terrace, Hartlepool Marina",
        address="22 Grange Road, Hartlepool", postcode="TS24 8EY", council="Hartlepool",
        property_type="Terraced", bedrooms=3, strategy="auction",
        purchase_price=55_000, estimated_value=79_000, gdv=79_000,
        refurb_cost=14_000, other_costs=3_200,
        description="Motivated seller. Chain free. Vacant possession. Close to marina regeneration development. Requires updating. Auction guide price.",
        status="active",
    ),
    dict(
        title="Under offer — 4-bed HMO, Walker Newcastle",
        address="34 Welbeck Road, Walker, Newcastle", postcode="NE6 3PB", council="Newcastle",
        property_type="Terraced", bedrooms=4, strategy="hmo",
        purchase_price=78_000, estimated_value=78_000, gdv=None,
        refurb_cost=10_000, other_costs=4_800,
        annual_yield=14.5, monthly_cashflow=920,
        description="4-bed licensed HMO. Rooms let individually. No chain. Motivated seller. Investment opportunity.",
        status="under_offer",
    ),
]


async def seed():
    engine = create_async_engine(DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        print("Seeding deals...")
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
            )
            deal = Deal(
                id=uuid.uuid4(),
                title=raw["title"],
                address=raw["address"],
                postcode=raw.get("postcode"),
                council=raw.get("council"),
                property_type=raw.get("property_type"),
                bedrooms=raw.get("bedrooms"),
                strategy=raw["strategy"],
                purchase_price=raw["purchase_price"],
                estimated_value=raw.get("estimated_value"),
                gdv=raw.get("gdv"),
                refurb_cost=raw.get("refurb_cost"),
                other_costs=raw.get("other_costs"),
                total_cost=s.total_cost,
                profit=s.profit,
                roi=s.roi,
                annual_yield=raw.get("annual_yield"),
                monthly_cashflow=raw.get("monthly_cashflow"),
                is_undervalued=s.is_undervalued,
                has_planning_upside=s.has_planning_upside,
                is_high_roi=s.is_high_roi,
                is_distressed=s.is_distressed,
                near_regen_zone=s.near_regen_zone,
                overall_score=s.overall_score,
                roi_score=s.roi_score,
                risk_score=s.risk_score,
                planning_uplift_score=s.planning_uplift_score,
                market_score=s.market_score,
                score_drivers=s.score_drivers,
                description=raw.get("description"),
                status=raw.get("status", "active"),
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            session.add(deal)
            count += 1
            roi_str = f"{s.roi:.0f}% ROI" if s.roi else "yield play"
            print(f"  [{s.overall_score:.0f}] {raw['title'][:50]} — {roi_str}")

        await session.commit()
        print(f"\n✓ {count} deals seeded and scored")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
