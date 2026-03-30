"""
Seed script — populates Northbridge Intelligence with realistic NE demo data.
Run: python scripts/seed.py
"""
import asyncio
import sys
import os
import uuid
from datetime import datetime, date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from passlib.context import CryptContext

from app.models.user import User
from app.models.listing import Listing
from app.models.comparable import ComparableSale
from app.models.planning import PlanningApplication
from app.models.regen_zone import RegenerationZone
from app.models.score import ListingScore
from app.database import Base

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://northbridge:northbridge@localhost:5432/northbridge")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


REGEN_ZONES = [
    dict(id=uuid.uuid4(), name="Teesworks / South Tees", council="Redcar & Cleveland",
         description="UK's largest freeport on former SSI steelworks. 4,500 acres of development land.",
         status="Active", funding_amount="£500m+", announcement_date="2020", completion_date="2035",
         center_lat=54.583, center_lng=-1.167, radius_km=3.0, postcodes="TS10,TS6,TS3",
         opportunity_notes="Industrial/logistics/manufacturing. Land prices still low vs opportunity."),
    dict(id=uuid.uuid4(), name="Newcastle Quayside Central", council="Newcastle City Council",
         description="Mixed-use regeneration along Tyne riverfront. New residential, office, leisure.",
         status="Active", funding_amount="£200m+", announcement_date="2021", completion_date="2028",
         center_lat=54.969, center_lng=-1.610, radius_km=1.0, postcodes="NE1,NE8",
         opportunity_notes="Residential uplift near waterfront. Commercial-to-resi conversions viable."),
    dict(id=uuid.uuid4(), name="Gateshead Stadium Quarter", council="Gateshead Council",
         description="Proposed 20,000-seat stadium + commercial/residential development.",
         status="Planning stage", funding_amount="TBC", announcement_date="2023", completion_date="2030",
         center_lat=54.960, center_lng=-1.602, radius_km=0.8, postcodes="NE8,NE10",
         opportunity_notes="Massive uplift potential if stadium confirmed. Watch planning portal closely."),
    dict(id=uuid.uuid4(), name="Sunderland Riverside", council="Sunderland City Council",
         description="Riverside Sunderland — 1,000+ homes, offices, Vaux brewery site.",
         status="Active", funding_amount="£1bn", announcement_date="2019", completion_date="2032",
         center_lat=54.906, center_lng=-1.383, radius_km=1.5, postcodes="SR1,SR2",
         opportunity_notes="Significant undervaluation vs Newcastle. BMV opportunities in city fringe."),
    dict(id=uuid.uuid4(), name="Northgate Durham", council="Durham County Council",
         description="Major mixed-use development in Durham city centre.",
         status="Active", funding_amount="£60m", announcement_date="2022", completion_date="2026",
         center_lat=54.776, center_lng=-1.577, radius_km=0.5, postcodes="DH1",
         opportunity_notes="City centre commercial property underpriced relative to scheme."),
    dict(id=uuid.uuid4(), name="Blyth Estuary / Northumberland", council="Northumberland County Council",
         description="Offshore wind supply chain hub. Industrial and logistics.",
         status="Active", funding_amount="£300m+", announcement_date="2021", completion_date="2030",
         center_lat=55.127, center_lng=-1.504, radius_km=2.0, postcodes="NE24,NE25",
         opportunity_notes="Industrial land and warehousing. Early-mover advantage."),
    dict(id=uuid.uuid4(), name="Hartlepool Marina Expansion", council="Hartlepool Borough Council",
         description="Residential and marina expansion on waterfront brownfield.",
         status="Active", funding_amount="£50m", announcement_date="2022", completion_date="2027",
         center_lat=54.691, center_lng=-1.210, radius_km=0.8, postcodes="TS24,TS25",
         opportunity_notes="Affordable entry point, waterfront premium being built in."),
    dict(id=uuid.uuid4(), name="South Shields Waterfront", council="South Tyneside Council",
         description="Leisure, hotel and residential on the waterfront.",
         status="Active", funding_amount="£100m", announcement_date="2020", completion_date="2027",
         center_lat=55.007, center_lng=-1.432, radius_km=0.8, postcodes="NE33,NE34",
         opportunity_notes="Hospitality and residential. Tourism-led uplift."),
]

LISTINGS = [
    # High BMV — distressed terraces Gateshead
    dict(source="rightmove", title="3-bed terraced house, Bensham", address="14 Bensham Road, Gateshead",
         postcode="NE8 1AA", council="Gateshead", property_type="T", bedrooms=3, asking_price=62000,
         description="Chain free. Vacant possession. Sold as seen. Requires full modernisation throughout. Cash buyers only. No onward chain. Motivated seller seeking quick sale. Investment opportunity.",
         agent_name="Hunters Gateshead", days_on_market=94, price_reduction_count=2, previous_price=72000,
         latitude=54.959, longitude=-1.601),
    dict(source="zoopla", title="2-bed flat, Gateshead town centre", address="Flat 4, 22 High Street, Gateshead",
         postcode="NE8 2AX", council="Gateshead", property_type="F", bedrooms=2, asking_price=58000,
         description="Investment opportunity. Currently tenanted at £500pcm. No chain. Priced to sell.",
         agent_name="PurpleBricks", days_on_market=67, price_reduction_count=1, previous_price=65000,
         latitude=54.961, longitude=-1.603),
    dict(source="rightmove", title="4-bed semi, Teams Gateshead", address="7 Dunston Road, Gateshead",
         postcode="NE8 4AQ", council="Gateshead", property_type="S", bedrooms=4, asking_price=89000,
         description="Excellent investment opportunity. HMO potential. 4 bedrooms. Requires updating. Chain free. Cash buyers preferred.",
         agent_name="Northgate Estate Agents", days_on_market=121, price_reduction_count=3, previous_price=110000,
         latitude=54.957, longitude=-1.625),

    # Sunderland — near regen zone
    dict(source="rightmove", title="3-bed terrace, Roker", address="45 Roker Avenue, Sunderland",
         postcode="SR6 0AA", council="Sunderland", property_type="T", bedrooms=3, asking_price=74000,
         description="Motivated seller. Vacant possession. Refurbishment opportunity. Solid terraced house close to seafront. Priced for quick sale.",
         agent_name="Vantage Estate Agents", days_on_market=55, price_reduction_count=1, previous_price=82000,
         latitude=54.930, longitude=-1.360),
    dict(source="zoopla", title="2-bed flat, Sunderland city centre", address="Apartment 12, Fawcett Street, Sunderland",
         postcode="SR1 1RH", council="Sunderland", property_type="F", bedrooms=2, asking_price=48000,
         description="Chain free. Executor sale. Sold as seen. In need of modernisation. Great investment.",
         agent_name="Your Move Sunderland", days_on_market=78, price_reduction_count=2, previous_price=59000,
         latitude=54.907, longitude=-1.384),
    dict(source="rightmove", title="Former retail unit, SR1", address="38 High Street West, Sunderland",
         postcode="SR1 3EX", council="Sunderland", property_type="O", bedrooms=None, asking_price=95000,
         description="Former retail unit. Planning potential for change of use to residential. Ground floor 1,200 sqft. Prior approval opportunity. Commercial to residential conversion. Cash buyers only.",
         agent_name="Christie & Co", days_on_market=145, price_reduction_count=2, previous_price=130000,
         latitude=54.906, longitude=-1.387),

    # Newcastle — city fringe
    dict(source="rightmove", title="1-bed flat, Byker", address="Flat 2, 89 Shields Road, Newcastle",
         postcode="NE6 1DL", council="Newcastle", property_type="F", bedrooms=1, asking_price=55000,
         description="Investment property. Currently let at £475pcm. No chain. Motivated seller.",
         agent_name="Reeds Rains Newcastle", days_on_market=43, price_reduction_count=1, previous_price=62000,
         latitude=54.979, longitude=-1.571),
    dict(source="zoopla", title="3-bed terrace, Fenham", address="112 Fenham Hall Drive, Newcastle",
         postcode="NE4 9XB", council="Newcastle", property_type="T", bedrooms=3, asking_price=115000,
         description="Chain free. Vacant possession. Requires modernisation. Large 3-bed terrace. Potential for HMO (subject to consent). Close to universities.",
         agent_name="Sanderson Young", days_on_market=61, price_reduction_count=1, previous_price=128000,
         latitude=54.972, longitude=-1.638),
    dict(source="rightmove", title="Detached house, Jesmond", address="19 Osborne Road, Jesmond",
         postcode="NE2 2AL", council="Newcastle", property_type="D", bedrooms=5, asking_price=320000,
         description="Handsome Victorian detached house. No chain. Large rooms throughout. HMO potential (8 rooms). Close to Newcastle University. Motivated vendor.",
         agent_name="Savills Newcastle", days_on_market=38, price_reduction_count=0, previous_price=None,
         latitude=54.980, longitude=-1.604),

    # Durham
    dict(source="rightmove", title="2-bed terrace, Durham city", address="5 Framwellgate, Durham",
         postcode="DH1 5TU", council="Durham", property_type="T", bedrooms=2, asking_price=98000,
         description="Charming terraced cottage. Chain free. In need of some updating. Investment opportunity near Durham city centre. Cash buyers preferred.",
         agent_name="Dowen Estate Agents", days_on_market=52, price_reduction_count=1, previous_price=109000,
         latitude=54.779, longitude=-1.578),
    dict(source="zoopla", title="4-bed detached, Newton Hall", address="23 Kepier Crescent, Durham",
         postcode="DH1 5GE", council="Durham", property_type="D", bedrooms=4, asking_price=245000,
         description="Spacious family home. No chain. Well presented throughout. Vendor relocated.",
         agent_name="Rook Matthews Sayer", days_on_market=29, price_reduction_count=0, previous_price=None,
         latitude=54.796, longitude=-1.549),

    # Teesside — near Teesworks
    dict(source="rightmove", title="Industrial unit, Redcar", address="Unit 7, Kirkleatham Business Park, Redcar",
         postcode="TS10 5RY", council="Redcar & Cleveland", property_type="O", bedrooms=None, asking_price=185000,
         description="Industrial unit 3,500 sqft. Adjacent to Teesworks freeport zone. Motivated seller. Potential for logistics, manufacturing. Cash buyers.",
         agent_name="GVA Grimley", days_on_market=88, price_reduction_count=1, previous_price=220000,
         latitude=54.584, longitude=-1.165),
    dict(source="zoopla", title="3-bed semi, Middlesbrough", address="67 Linthorpe Road, Middlesbrough",
         postcode="TS1 3QQ", council="Middlesbrough", property_type="S", bedrooms=3, asking_price=79000,
         description="Chain free. Vacant possession. Cash buyers only. Sold as seen. Refurbishment required.",
         agent_name="William H Brown", days_on_market=103, price_reduction_count=2, previous_price=92000,
         latitude=54.572, longitude=-1.234),
    dict(source="rightmove", title="2-bed terrace, Stockton", address="18 Norton Road, Stockton-on-Tees",
         postcode="TS18 2AB", council="Stockton", property_type="T", bedrooms=2, asking_price=54000,
         description="Investment property. Tenanted £425pcm. No chain. Priced to sell quickly.",
         agent_name="Dowen & Kerr", days_on_market=34, price_reduction_count=0, previous_price=None,
         latitude=54.563, longitude=-1.319),

    # More varied stock
    dict(source="rightmove", title="Semi-detached, Whickham", address="31 Rectory Lane, Whickham",
         postcode="NE16 4PB", council="Gateshead", property_type="S", bedrooms=3, asking_price=168000,
         description="Well-presented semi in popular village location. No chain. Vendor committed elsewhere.",
         agent_name="Signature Homes", days_on_market=22, price_reduction_count=0, previous_price=None,
         latitude=54.919, longitude=-1.710),
    dict(source="zoopla", title="Former pub, conversion potential", address="The Crown Inn, Front Street, Winlaton",
         postcode="NE21 4EB", council="Gateshead", property_type="O", bedrooms=None, asking_price=125000,
         description="Former pub — vacant. Ideal for residential conversion. Prior approval potential. Planning potential. Change of use. Development opportunity. Cash buyers only.",
         agent_name="Naylors Commercial", days_on_market=167, price_reduction_count=3, previous_price=180000,
         latitude=54.938, longitude=-1.758),
    dict(source="rightmove", title="Barn conversion opportunity", address="Highfield Farm, Ponteland Road",
         postcode="NE20 9BP", council="Northumberland", property_type="O", bedrooms=None, asking_price=210000,
         description="Redundant agricultural buildings with planning potential. Agricultural to residential conversion. Barn conversion. Outline planning being sought. Rural setting.",
         agent_name="Strutt & Parker", days_on_market=74, price_reduction_count=0, previous_price=None,
         latitude=55.020, longitude=-1.720),
    dict(source="rightmove", title="Ground floor flat, South Shields", address="Flat 1, 3 Ocean Road, South Shields",
         postcode="NE33 2JA", council="South Tyneside", property_type="F", bedrooms=1, asking_price=42000,
         description="Chain free. Probate sale. In need of full refurbishment. Cash buyers only. Investment opportunity near seafront.",
         agent_name="Ward & Partners", days_on_market=118, price_reduction_count=3, previous_price=58000,
         latitude=55.003, longitude=-1.432),
    dict(source="zoopla", title="3-bed terrace, Hartlepool", address="22 Grange Road, Hartlepool",
         postcode="TS24 8EY", council="Hartlepool", property_type="T", bedrooms=3, asking_price=59000,
         description="Motivated seller. Chain free. Vacant possession. Close to marina development. Requires updating.",
         agent_name="Dowen Kerr Hartlepool", days_on_market=81, price_reduction_count=2, previous_price=70000,
         latitude=54.691, longitude=-1.211),
    dict(source="rightmove", title="Office building, NE1", address="12 Grey Street, Newcastle upon Tyne",
         postcode="NE1 6AE", council="Newcastle", property_type="O", bedrooms=None, asking_price=375000,
         description="Grade II listed office building. Potential for conversion to residential (Class MA). City centre location. Motivated vendor. Planning uplift potential.",
         agent_name="Knight Frank Newcastle", days_on_market=56, price_reduction_count=1, previous_price=430000,
         latitude=54.973, longitude=-1.614),
    dict(source="rightmove", title="4-bed HMO, Sunderland", address="88 Toward Road, Sunderland",
         postcode="SR2 7EH", council="Sunderland", property_type="T", bedrooms=4, asking_price=88000,
         description="Licensed HMO. 4 rooms fully let. Gross income £1,800pcm. No chain. Investment opportunity. Motivated seller.",
         agent_name="HMO Daddy Sunderland", days_on_market=44, price_reduction_count=0, previous_price=None,
         latitude=54.897, longitude=-1.394),
]

COMPARABLES = [
    ("NE8 1AA", "T", 68500, "2024-08-12"), ("NE8 1AB", "T", 72000, "2024-06-03"),
    ("NE8 1AC", "T", 65000, "2024-09-22"), ("NE8 2AX", "F", 63000, "2024-07-15"),
    ("NE8 2AY", "F", 58000, "2024-05-01"), ("SR6 0AA", "T", 82000, "2024-10-05"),
    ("SR6 0AB", "T", 79500, "2024-08-18"), ("SR1 1RH", "F", 55000, "2024-07-29"),
    ("SR1 3EX", "O", 115000, "2024-04-12"), ("NE6 1DL", "F", 62000, "2024-09-01"),
    ("NE4 9XB", "T", 122000, "2024-06-22"), ("NE2 2AL", "D", 345000, "2024-08-07"),
    ("DH1 5TU", "T", 108000, "2024-07-11"), ("DH1 5GE", "D", 258000, "2024-09-14"),
    ("TS10 5RY", "O", 210000, "2024-05-25"), ("TS1 3QQ", "S", 88000, "2024-10-02"),
    ("TS18 2AB", "T", 59000, "2024-08-30"), ("NE16 4PB", "S", 172000, "2024-07-04"),
    ("NE33 2JA", "F", 51000, "2024-06-17"), ("TS24 8EY", "T", 68000, "2024-09-08"),
    ("NE1 6AE", "O", 420000, "2024-05-19"), ("SR2 7EH", "T", 92000, "2024-08-25"),
    ("NE8 4AQ", "S", 105000, "2024-07-31"), ("NE8 1AA", "T", 71000, "2023-11-20"),
    ("NE8 1AB", "T", 69500, "2023-09-05"), ("SR1 1RH", "F", 52000, "2023-12-01"),
    ("NE6 1DL", "F", 60000, "2023-10-14"), ("TS1 3QQ", "S", 85000, "2023-08-22"),
    ("NE4 9XB", "T", 118000, "2023-11-30"), ("DH1 5TU", "T", 104000, "2023-07-09"),
]

PLANNING_APPS = [
    dict(council="Gateshead Council", application_reference="DC/24/00142", address="Former Office Block, Jackson Street, Gateshead",
         postcode="NE8 1EB", application_type="Prior Approval (Class MA)", proposal="Change of use from offices (Class E) to 12 residential units (Class C3)",
         status="Approved", decision="Approved", date_received=date(2024, 3, 15),
         uplift_signals=["change_of_use", "conversion", "prior_approval", "residential"],
         uplift_score=82.0),
    dict(council="Sunderland City Council", application_reference="23/02891/FUL", address="Vaux Brewery Site Phase 2, Sunderland",
         postcode="SR1 2JR", application_type="Full Planning", proposal="Erection of 180 residential dwellings, commercial units and public realm",
         status="Approved", decision="Approved", date_received=date(2023, 11, 8),
         uplift_signals=["new_build", "residential", "regeneration"],
         uplift_score=75.0),
    dict(council="Newcastle City Council", application_reference="2024/1234/FUL", address="Central Exchange Buildings, Grey Street, Newcastle",
         postcode="NE1 6AF", application_type="Full Planning", proposal="Conversion of upper floors from offices to 24 residential apartments. Ground floor retention as Class E.",
         status="Pending", decision=None, date_received=date(2024, 6, 20),
         uplift_signals=["change_of_use", "conversion", "residential"],
         uplift_score=78.0),
    dict(council="Gateshead Council", application_reference="DC/24/00891", address="Adjacent to Stadium Site, Brewery Lane, Gateshead",
         postcode="NE8 2HT", application_type="Outline Planning", proposal="Outline application for mixed-use development including residential (C3), hotel (C1) and commercial (Class E) uses.",
         status="Pending", decision=None, date_received=date(2024, 8, 1),
         uplift_signals=["new_build", "residential", "regeneration"],
         uplift_score=88.0),
    dict(council="Durham County Council", application_reference="DM/24/01122/FPA", address="Northgate Site, North Road, Durham",
         postcode="DH1 4EJ", application_type="Full Planning", proposal="New office building, residential units and retail space as part of Northgate regeneration scheme.",
         status="Approved", decision="Approved", date_received=date(2024, 1, 17),
         uplift_signals=["regeneration", "residential", "new_build"],
         uplift_score=72.0),
    dict(council="Middlesbrough Council", application_reference="24/0456/FUL", address="Linthorpe Road Retail Units, Middlesbrough",
         postcode="TS1 3AB", application_type="Prior Approval (Class MA)", proposal="Change of use from retail/office to 8 residential flats. Prior approval under Class MA.",
         status="Approved", decision="Prior Approval Required and Approved", date_received=date(2024, 4, 9),
         uplift_signals=["change_of_use", "conversion", "prior_approval"],
         uplift_score=80.0),
    dict(council="Stockton-on-Tees Borough Council", application_reference="24/1891/FUL", address="Former Argos Store, High Street, Stockton",
         postcode="TS18 1AT", application_type="Full Planning", proposal="Conversion of vacant retail unit to 16 residential apartments with ground floor commercial.",
         status="Pending", decision=None, date_received=date(2024, 9, 3),
         uplift_signals=["change_of_use", "conversion", "residential"],
         uplift_score=76.0),
    dict(council="South Tyneside Council", application_reference="ST/2024/0234/FUL", address="Commercial Road Depot, South Shields",
         postcode="NE33 1RR", application_type="Full Planning", proposal="Residential development — erection of 45 new dwellings on former industrial land.",
         status="Approved", decision="Approved", date_received=date(2024, 2, 28),
         uplift_signals=["new_build", "residential", "regeneration"],
         uplift_score=70.0),
]


async def seed():
    engine = create_async_engine(DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        print("Seeding users...")
        admin = User(id=uuid.uuid4(), email="admin@northbridge.io",
                     password_hash=pwd_context.hash("admin123"),
                     full_name="Admin User", is_admin=True, is_active=True,
                     created_at=datetime.utcnow(), updated_at=datetime.utcnow())
        demo = User(id=uuid.uuid4(), email="demo@northbridge.io",
                    password_hash=pwd_context.hash("demo123"),
                    full_name="Demo User", is_admin=False, is_active=True,
                    created_at=datetime.utcnow(), updated_at=datetime.utcnow())
        session.add_all([admin, demo])
        await session.commit()
        print("  ✓ 2 users created")

        print("Seeding regeneration zones...")
        for z in REGEN_ZONES:
            zone = RegenerationZone(**z, created_at=datetime.utcnow())
            session.add(zone)
        await session.commit()
        print(f"  ✓ {len(REGEN_ZONES)} zones created")

        print("Seeding comparable sales...")
        for postcode, prop_type, price, date_str in COMPARABLES:
            sale = ComparableSale(
                id=uuid.uuid4(), postcode=postcode, property_type=prop_type,
                price=price, date_sold=date.fromisoformat(date_str),
                new_build=False, source="land_registry", created_at=datetime.utcnow()
            )
            session.add(sale)
        await session.commit()
        print(f"  ✓ {len(COMPARABLES)} comparables created")

        print("Seeding planning applications...")
        for p in PLANNING_APPS:
            app = PlanningApplication(id=uuid.uuid4(), created_at=datetime.utcnow(),
                                      updated_at=datetime.utcnow(), **p)
            session.add(app)
        await session.commit()
        print(f"  ✓ {len(PLANNING_APPS)} planning applications created")

        print("Seeding listings + scoring...")
        for l in LISTINGS:
            days = l.pop("days_on_market", 0)
            listing = Listing(
                id=uuid.uuid4(), source_id=str(uuid.uuid4())[:8],
                status="active", price_reduction_count=l.pop("price_reduction_count", 0),
                first_seen_at=datetime.utcnow() - timedelta(days=days),
                last_seen_at=datetime.utcnow(),
                date_listed=(datetime.utcnow() - timedelta(days=days)).date(),
                created_at=datetime.utcnow(), updated_at=datetime.utcnow(),
                **l
            )
            session.add(listing)
            await session.flush()

            # Quick score
            asking = listing.asking_price
            postcode = listing.postcode or ""
            prefix = postcode.split(" ")[0]
            comps = [c for c in COMPARABLES if c[0].startswith(prefix[:4]) and c[1] == listing.property_type]
            avg_comp = int(sum(c[2] for c in comps) / len(comps)) if comps else None

            bmv = 0.0
            discount = None
            if avg_comp and asking < avg_comp:
                discount = ((avg_comp - asking) / avg_comp) * 100
                bmv = min(discount * 2.5, 100)

            desc = (listing.description or "").lower()
            distress_hits = sum(1 for kw in ["chain free","no chain","vacant","sold as seen",
                                              "motivated","cash buyer","probate","repossession",
                                              "executor","quick sale"] if kw in desc)
            distress = min(distress_hits * 14, 100)
            dom = days
            momentum = min((max(0, dom - 30) / 90) * 60 + listing.price_reduction_count * 15, 100)
            planning_s = 25.0 if any(kw in desc for kw in ["planning","prior approval","change of use","conversion"]) else 0.0
            regen_s = 40.0 if any(z in (listing.postcode or "") for zone in REGEN_ZONES
                                   for z in (zone.get("postcodes","") or "").split(",")) else 0.0
            confidence = min(len(comps) * 20, 100) if comps else 30.0

            overall = round(bmv * 0.30 + distress * 0.22 + momentum * 0.13 +
                            planning_s * 0.15 + regen_s * 0.15, 1)
            overall = min(overall * (0.7 + confidence / 333), 100)

            score = ListingScore(
                id=uuid.uuid4(), listing_id=listing.id,
                overall_score=round(overall, 1), bmv_score=round(bmv, 1),
                distress_score=round(distress, 1), momentum_score=round(momentum, 1),
                planning_score=round(planning_s, 1), regeneration_score=round(regen_s, 1),
                confidence_score=round(confidence, 1),
                estimated_fair_value=avg_comp,
                avg_comparable_price=avg_comp,
                discount_pct=round(discount, 1) if discount else None,
                score_drivers=[], scored_at=datetime.utcnow(), created_at=datetime.utcnow()
            )
            session.add(score)

        await session.commit()
        print(f"  ✓ {len(LISTINGS)} listings created and scored")

    await engine.dispose()
    print("\n✓ Seed complete. Login: admin@northbridge.io / admin123")


if __name__ == "__main__":
    asyncio.run(seed())
