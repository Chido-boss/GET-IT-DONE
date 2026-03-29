"""
Planning application monitoring for North East councils.
Most NE councils use Idox Uniform planning system — scrape-friendly.
"""
import httpx
import aiosqlite
import os
import logging
import re
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)
DB_FILE = os.getenv("DB_FILE", "northbridge.db")

COUNCILS = {
    "gateshead": {
        "name": "Gateshead Council",
        "url": "https://www.gateshead.gov.uk/article/3314/Search-for-a-planning-application",
        "search_url": "https://public.gateshead.gov.uk/online-applications/search.do",
        "type": "idox",
    },
    "newcastle": {
        "name": "Newcastle City Council",
        "url": "https://www.newcastle.gov.uk/services/planning-and-buildings/planning-applications",
        "search_url": "https://publicaccess.newcastle.gov.uk/online-applications/search.do",
        "type": "idox",
    },
    "sunderland": {
        "name": "Sunderland City Council",
        "search_url": "https://www.sunderland.gov.uk/planning-search",
        "type": "custom",
    },
    "durham": {
        "name": "Durham County Council",
        "search_url": "https://publicaccess.durham.gov.uk/online-applications/search.do",
        "type": "idox",
    },
    "south_tyneside": {
        "name": "South Tyneside Council",
        "search_url": "https://www.southtyneside.gov.uk/article/36394/Search-planning-applications",
        "type": "idox",
    },
    "north_tyneside": {
        "name": "North Tyneside Council",
        "search_url": "https://www.northtyneside.gov.uk/planning-portal",
        "type": "idox",
    },
    "middlesbrough": {
        "name": "Middlesbrough Council",
        "search_url": "https://planning.middlesbrough.gov.uk/online-applications/search.do",
        "type": "idox",
    },
    "stockton": {
        "name": "Stockton-on-Tees Borough Council",
        "search_url": "https://www.stockton.gov.uk/planning-applications",
        "type": "custom",
    },
    "darlington": {
        "name": "Darlington Borough Council",
        "search_url": "https://planning.darlington.gov.uk/online-applications/search.do",
        "type": "idox",
    },
    "northumberland": {
        "name": "Northumberland County Council",
        "search_url": "https://www.northumberland.gov.uk/Planning/Planning-applications.aspx",
        "type": "custom",
    },
}

UPLIFT_KEYWORDS = {
    "change_of_use": [
        "change of use", "conversion", "convert", "class e", "class ma",
        "prior approval", "permitted development", "office to residential",
        "commercial to residential", "barn conversion", "agricultural to residential",
    ],
    "development": [
        "erection of", "construction of", "new dwelling", "residential development",
        "mixed use development", "outline planning", "hybrid application",
    ],
    "regeneration": [
        "regeneration", "brownfield", "remediation", "decontamination",
        "enabling development", "masterplan", "strategic development",
    ],
    "scale": [
        "50 dwelling", "100 dwelling", "200 dwelling", "500 dwelling",
        "1,000", "mixed use", "hotel", "student accommodation", "build to rent",
    ],
}

def score_planning_uplift(description: str, application_type: str) -> tuple[float, str]:
    """Score a planning application for investment/uplift opportunity."""
    if not description:
        return 0.0, None
    desc_lower = description.lower()
    score = 0.0
    opportunity_types = []

    if any(kw in desc_lower for kw in UPLIFT_KEYWORDS["change_of_use"]):
        score += 35
        opportunity_types.append("Change of Use / Conversion")

    if any(kw in desc_lower for kw in UPLIFT_KEYWORDS["regeneration"]):
        score += 25
        opportunity_types.append("Regeneration")

    if any(kw in desc_lower for kw in UPLIFT_KEYWORDS["development"]):
        score += 20
        opportunity_types.append("New Development")

    if any(kw in desc_lower for kw in UPLIFT_KEYWORDS["scale"]):
        score += 20
        opportunity_types.append("Large Scale")

    if application_type and "outline" in application_type.lower():
        score += 15

    if application_type and "prior approval" in application_type.lower():
        score += 30

    return min(score, 100.0), ", ".join(opportunity_types) if opportunity_types else None


async def fetch_planning_gov_uk(council_key: str, days_back: int = 14) -> list[dict]:
    """
    Use Planning.data.gov.uk API — official government planning data feed.
    This is the reliable, legal, structured route.
    """
    from_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
    council_info = COUNCILS.get(council_key, {})

    # Map council keys to LPA reference codes used by planning.data.gov.uk
    lpa_mapping = {
        "gateshead": "gateshead",
        "newcastle": "newcastle-upon-tyne",
        "sunderland": "sunderland",
        "durham": "county-durham",
        "south_tyneside": "south-tyneside",
        "north_tyneside": "north-tyneside",
        "middlesbrough": "middlesbrough",
        "stockton": "stockton-on-tees",
        "darlington": "darlington",
        "northumberland": "northumberland",
    }
    lpa = lpa_mapping.get(council_key, council_key)
    url = "https://www.planning.data.gov.uk/entity.json"

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(url, params={
                "dataset": "planning-application",
                "organisation_entity": lpa,
                "start_date_field": "entry-date",
                "start_date": from_date,
                "limit": 100,
                "offset": 0,
            })
            if resp.status_code != 200:
                return []
            data = resp.json()
            entities = data.get("entities", [])
            results = []
            for e in entities:
                props = e.get("properties", {}) if isinstance(e, dict) else {}
                description = e.get("description", "") or props.get("description", "")
                app_type = props.get("application-type", "")
                uplift_score, opp_type = score_planning_uplift(description, app_type)
                results.append({
                    "council": council_info.get("name", council_key),
                    "reference": e.get("reference", ""),
                    "address": e.get("name", ""),
                    "postcode": props.get("postcode", ""),
                    "description": description,
                    "application_type": app_type,
                    "status": props.get("development-type", ""),
                    "received_date": e.get("entry-date", ""),
                    "decision_date": props.get("decision-date", ""),
                    "uplift_score": uplift_score,
                    "opportunity_type": opp_type,
                    "url": f"https://www.planning.data.gov.uk/entity/{e.get('entity', '')}",
                })
            return results
    except Exception as ex:
        logger.error(f"Planning data fetch failed for {council_key}: {ex}")
        return []


async def import_planning_applications(council_key: str = None, days_back: int = 14):
    """Fetch and store planning applications for one or all NE councils."""
    councils_to_fetch = [council_key] if council_key else list(COUNCILS.keys())
    total = 0
    async with aiosqlite.connect(DB_FILE) as db:
        for key in councils_to_fetch:
            apps = await fetch_planning_gov_uk(key, days_back)
            for app in apps:
                try:
                    await db.execute(
                        """INSERT OR IGNORE INTO planning_applications
                           (council, reference, address, postcode, description, application_type,
                            status, received_date, decision_date, uplift_score, opportunity_type, url)
                           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (app["council"], app["reference"], app["address"], app["postcode"],
                         app["description"], app["application_type"], app["status"],
                         app["received_date"], app["decision_date"], app["uplift_score"],
                         app["opportunity_type"], app["url"])
                    )
                    total += 1
                except Exception as e:
                    logger.debug(f"Skip: {e}")
        await db.commit()
    return total


async def get_high_uplift_applications(min_score: float = 40.0, limit: int = 50) -> list[dict]:
    async with aiosqlite.connect(DB_FILE) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT * FROM planning_applications
               WHERE uplift_score >= ? ORDER BY uplift_score DESC, first_seen DESC LIMIT ?""",
            (min_score, limit)
        )
        return [dict(r) for r in await cursor.fetchall()]
