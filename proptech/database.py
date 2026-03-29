import aiosqlite
import os

DB_FILE = os.getenv("DB_FILE", "northbridge.db")

CREATE_TABLES = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at INTEGER NOT NULL DEFAULT (strftime('%s','now'))
);

CREATE TABLE IF NOT EXISTS properties (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    source_id TEXT,
    address TEXT NOT NULL,
    postcode TEXT,
    property_type TEXT,
    bedrooms INTEGER,
    asking_price INTEGER,
    avg_comparable INTEGER,
    bmv_score REAL,
    days_on_market INTEGER,
    description TEXT,
    url TEXT,
    status TEXT DEFAULT 'active',
    flagged INTEGER DEFAULT 0,
    notes TEXT,
    first_seen INTEGER NOT NULL DEFAULT (strftime('%s','now')),
    last_updated INTEGER NOT NULL DEFAULT (strftime('%s','now'))
);

CREATE TABLE IF NOT EXISTS planning_applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    council TEXT NOT NULL,
    reference TEXT NOT NULL,
    address TEXT NOT NULL,
    postcode TEXT,
    description TEXT,
    application_type TEXT,
    status TEXT,
    received_date TEXT,
    decision_date TEXT,
    uplift_score REAL,
    opportunity_type TEXT,
    url TEXT,
    first_seen INTEGER NOT NULL DEFAULT (strftime('%s','now')),
    UNIQUE(council, reference)
);

CREATE TABLE IF NOT EXISTS land_registry (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    transaction_id TEXT UNIQUE,
    price INTEGER NOT NULL,
    date TEXT NOT NULL,
    postcode TEXT,
    property_type TEXT,
    new_build TEXT,
    estate_type TEXT,
    address TEXT,
    district TEXT,
    county TEXT,
    imported_at INTEGER NOT NULL DEFAULT (strftime('%s','now'))
);

CREATE TABLE IF NOT EXISTS deals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    address TEXT NOT NULL,
    postcode TEXT,
    strategy TEXT NOT NULL,
    purchase_price INTEGER,
    estimated_value INTEGER,
    potential_profit INTEGER,
    roi_pct REAL,
    ai_analysis TEXT,
    status TEXT DEFAULT 'prospecting',
    source TEXT,
    created_at INTEGER NOT NULL DEFAULT (strftime('%s','now')),
    updated_at INTEGER NOT NULL DEFAULT (strftime('%s','now'))
);

CREATE TABLE IF NOT EXISTS regen_zones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    council TEXT,
    description TEXT,
    status TEXT,
    funding_amount TEXT,
    announcement_date TEXT,
    completion_date TEXT,
    postcodes TEXT,
    opportunity_notes TEXT,
    created_at INTEGER NOT NULL DEFAULT (strftime('%s','now'))
);

CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    alert_type TEXT NOT NULL,
    criteria TEXT NOT NULL,
    active INTEGER DEFAULT 1,
    last_fired INTEGER,
    created_at INTEGER NOT NULL DEFAULT (strftime('%s','now'))
);

CREATE TABLE IF NOT EXISTS auction_lots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    auctioneer TEXT NOT NULL,
    lot_number TEXT,
    address TEXT NOT NULL,
    postcode TEXT,
    guide_price INTEGER,
    reserve_price INTEGER,
    sold_price INTEGER,
    auction_date TEXT,
    property_type TEXT,
    description TEXT,
    url TEXT,
    bmv_score REAL,
    status TEXT DEFAULT 'upcoming',
    first_seen INTEGER NOT NULL DEFAULT (strftime('%s','now')),
    UNIQUE(auctioneer, lot_number, auction_date)
);
"""

async def init_db():
    async with aiosqlite.connect(DB_FILE) as db:
        await db.executescript(CREATE_TABLES)
        await db.commit()
        await _seed_regen_zones(db)

async def _seed_regen_zones(db):
    existing = await db.execute("SELECT COUNT(*) FROM regen_zones")
    row = await existing.fetchone()
    if row[0] > 0:
        return
    zones = [
        ("Teesworks / South Tees", "Redcar & Cleveland / Middlesbrough", "UK's largest freeport and development zone on former SSI steelworks site. 4,500 acres.", "Active", "£500m+", "2020", "2035", "TS10,TS6,TS3", "Industrial/logistics/manufacturing. Land prices still low vs opportunity."),
        ("Newcastle Quayside Central", "Newcastle City Council", "Mixed-use regeneration along Tyne riverfront. New residential, office, leisure.", "Active", "£200m+", "2021", "2028", "NE1,NE8", "Residential uplift near waterfront. Commercial-to-resi conversions viable."),
        ("Gateshead Stadium Quarter", "Gateshead Council", "Proposed 20,000 seat stadium + commercial/residential around it.", "Planning stage", "TBC", "2023", "2030", "NE8,NE10", "Massive uplift potential if stadium confirmed. Watch planning portal closely."),
        ("Sunderland City Centre", "Sunderland City Council", "Riverside Sunderland project — 1,000+ homes, offices, Vaux brewery site.", "Active", "£1bn", "2019", "2032", "SR1,SR2", "Significant undervaluation vs Newcastle. BMV opportunities in city fringe."),
        ("Northgate Durham", "Durham County Council", "Major mixed-use development in Durham city centre.", "Active", "£60m", "2022", "2026", "DH1", "City centre commercial property underpriced relative to scheme."),
        ("Blyth Estuary / Northumberland", "Northumberland County Council", "Offshore wind supply chain hub. Industrial and logistics.", "Active", "£300m+", "2021", "2030", "NE24,NE25", "Industrial land and warehousing. Early-mover advantage."),
        ("Hartlepool Marina Expansion", "Hartlepool Borough Council", "Residential and marina expansion on waterfront brownfield.", "Active", "£50m", "2022", "2027", "TS24,TS25", "Affordable entry point, waterfront premium being built in."),
        ("South Shields Waterfront", "South Tyneside Council", "Leisure, hotel and residential on the waterfront.", "Active", "£100m", "2020", "2027", "NE33,NE34", "Hospitality and residential. Tourism-led uplift."),
    ]
    await db.executemany(
        "INSERT OR IGNORE INTO regen_zones (name, council, description, status, funding_amount, announcement_date, completion_date, postcodes, opportunity_notes) VALUES (?,?,?,?,?,?,?,?,?)",
        zones
    )
    await db.commit()

async def get_db():
    return aiosqlite.connect(DB_FILE)
