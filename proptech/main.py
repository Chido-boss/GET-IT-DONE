import asyncio
import logging
import os
import json
from contextlib import asynccontextmanager
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import aiosqlite

from database import init_db, DB_FILE
from data.land_registry import import_sales_to_db, get_comparables, NE_POSTCODES
from data.planning import import_planning_applications, get_high_uplift_applications, COUNCILS
from intelligence.deal_scorer import score_listing, calculate_deal_metrics, get_top_opportunities
from intelligence.ai_analyst import analyse_deal, score_planning_opportunity

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

# ── Background data refresh ──────────────────────────────────────────────────

async def background_refresh():
    """Periodically refresh planning data and land registry samples."""
    await asyncio.sleep(10)  # startup grace period
    while True:
        try:
            logger.info("Refreshing planning applications...")
            total = await import_planning_applications(days_back=30)
            logger.info(f"Imported {total} planning applications")
        except Exception as e:
            logger.error(f"Planning refresh error: {e}")
        await asyncio.sleep(3600 * 6)  # refresh every 6 hours

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    logger.info("Database initialised")
    asyncio.create_task(background_refresh())
    yield

app = FastAPI(title="Northbridge Intelligence", lifespan=lifespan)
templates = Jinja2Templates(directory="templates")

# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    async with aiosqlite.connect(DB_FILE) as db:
        db.row_factory = aiosqlite.Row

        # Stats
        props = await (await db.execute("SELECT COUNT(*) FROM properties WHERE status='active'")).fetchone()
        planning = await (await db.execute("SELECT COUNT(*) FROM planning_applications")).fetchone()
        lr_count = await (await db.execute("SELECT COUNT(*) FROM land_registry")).fetchone()
        deals = await (await db.execute("SELECT COUNT(*) FROM deals")).fetchone()

        # Top opportunities
        top_props = await (await db.execute(
            "SELECT * FROM properties WHERE bmv_score IS NOT NULL ORDER BY bmv_score DESC LIMIT 6"
        )).fetchall()

        # High uplift planning
        top_planning = await (await db.execute(
            "SELECT * FROM planning_applications WHERE uplift_score >= 40 ORDER BY uplift_score DESC LIMIT 5"
        )).fetchall()

        # Regen zones
        regen = await (await db.execute("SELECT * FROM regen_zones ORDER BY status")).fetchall()

        # Recent deals
        recent_deals = await (await db.execute(
            "SELECT * FROM deals ORDER BY created_at DESC LIMIT 5"
        )).fetchall()

    return templates.TemplateResponse(request, "dashboard.html", {
        "stats": {
            "properties": props[0] if props else 0,
            "planning": planning[0] if planning else 0,
            "land_registry": lr_count[0] if lr_count else 0,
            "deals": deals[0] if deals else 0,
        },
        "top_properties": [dict(r) for r in top_props],
        "top_planning": [dict(r) for r in top_planning],
        "regen_zones": [dict(r) for r in regen],
        "recent_deals": [dict(r) for r in recent_deals],
    })


@app.get("/planning", response_class=HTMLResponse)
async def planning_view(request: Request, min_score: float = 0, council: str = ""):
    async with aiosqlite.connect(DB_FILE) as db:
        db.row_factory = aiosqlite.Row
        query = "SELECT * FROM planning_applications WHERE 1=1"
        params = []
        if min_score > 0:
            query += " AND uplift_score >= ?"
            params.append(min_score)
        if council:
            query += " AND council LIKE ?"
            params.append(f"%{council}%")
        query += " ORDER BY uplift_score DESC, first_seen DESC LIMIT 100"
        cursor = await db.execute(query, params)
        applications = [dict(r) for r in await cursor.fetchall()]

    return templates.TemplateResponse(request, "planning.html", {
        "applications": applications,
        "councils": list(COUNCILS.keys()),
        "filter_score": min_score,
        "filter_council": council,
    })


@app.get("/planning/{app_id}/analyse")
async def analyse_planning_app(app_id: int):
    async with aiosqlite.connect(DB_FILE) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM planning_applications WHERE id = ?", (app_id,))
        app_row = await cursor.fetchone()
    if not app_row:
        raise HTTPException(404, "Application not found")
    analysis = await score_planning_opportunity(dict(app_row))
    return JSONResponse({"analysis": analysis})


@app.get("/deals", response_class=HTMLResponse)
async def deals_view(request: Request):
    async with aiosqlite.connect(DB_FILE) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM deals ORDER BY created_at DESC")
        deals = [dict(r) for r in await cursor.fetchall()]
    return templates.TemplateResponse(request, "deals.html", {"deals": deals})


@app.post("/deals/analyse", response_class=HTMLResponse)
async def analyse_property(
    request: Request,
    address: str = Form(...),
    postcode: str = Form(...),
    asking_price: int = Form(...),
    property_type: str = Form(""),
    bedrooms: int = Form(0),
    description: str = Form(""),
    strategy: str = Form("flip"),
):
    comparables = await get_comparables(postcode, property_type or None)
    listing = {
        "address": address,
        "postcode": postcode,
        "asking_price": asking_price,
        "property_type": property_type,
        "bedrooms": bedrooms,
        "description": description,
    }
    deal_score = score_listing(listing, comparables)
    metrics = calculate_deal_metrics(asking_price, strategy)
    ai_analysis = await analyse_deal(listing, comparables)

    async with aiosqlite.connect(DB_FILE) as db:
        cursor = await db.execute(
            """INSERT INTO deals (address, postcode, strategy, purchase_price, estimated_value,
               potential_profit, roi_pct, ai_analysis, source)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (address, postcode, strategy, asking_price,
             deal_score.estimated_value,
             metrics.get("gross_profit", 0),
             metrics.get("roi_pct", 0),
             ai_analysis, "manual")
        )
        deal_id = cursor.lastrowid
        await db.commit()

    return templates.TemplateResponse(request, "analysis_result.html", {
        "listing": listing,
        "deal_score": deal_score,
        "comparables": comparables,
        "metrics": metrics,
        "ai_analysis": ai_analysis,
        "deal_id": deal_id,
    })


@app.get("/land-registry", response_class=HTMLResponse)
async def land_registry_view(request: Request, postcode: str = "NE1"):
    comparables = await get_comparables(postcode)
    async with aiosqlite.connect(DB_FILE) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM land_registry WHERE postcode LIKE ? ORDER BY date DESC LIMIT 50",
            (f"{postcode.split()[0]}%",)
        )
        sales = [dict(r) for r in await cursor.fetchall()]
        count = await (await db.execute("SELECT COUNT(*) FROM land_registry")).fetchone()

    return templates.TemplateResponse(request, "land_registry.html", {
        "sales": sales,
        "comparables": comparables,
        "postcode": postcode,
        "total_records": count[0] if count else 0,
        "ne_postcodes": NE_POSTCODES[:20],
    })


@app.post("/land-registry/import")
async def trigger_lr_import(postcode_prefix: str = Form(...)):
    count = await import_sales_to_db(postcode_prefix)
    return JSONResponse({"imported": count, "postcode": postcode_prefix})


@app.get("/regen-zones", response_class=HTMLResponse)
async def regen_zones_view(request: Request):
    async with aiosqlite.connect(DB_FILE) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM regen_zones ORDER BY status, name")
        zones = [dict(r) for r in await cursor.fetchall()]
    return templates.TemplateResponse(request, "regen_zones.html", {"zones": zones})


@app.get("/api/refresh-planning")
async def refresh_planning():
    count = await import_planning_applications(days_back=30)
    return JSONResponse({"imported": count})


@app.get("/api/stats")
async def api_stats():
    async with aiosqlite.connect(DB_FILE) as db:
        props = await (await db.execute("SELECT COUNT(*) FROM properties")).fetchone()
        planning = await (await db.execute("SELECT COUNT(*) FROM planning_applications")).fetchone()
        lr = await (await db.execute("SELECT COUNT(*) FROM land_registry")).fetchone()
        high_uplift = await (await db.execute(
            "SELECT COUNT(*) FROM planning_applications WHERE uplift_score >= 50"
        )).fetchone()
    return {
        "properties_tracked": props[0],
        "planning_applications": planning[0],
        "land_registry_records": lr[0],
        "high_uplift_opportunities": high_uplift[0],
    }
