"""
Land Registry Price Paid Data — official free API from HM Land Registry.
SPARQL endpoint: https://landregistry.data.gov.uk/app/ppd
Bulk CSV: http://prod.publicdata.landregistry.gov.uk.s3-website-eu-west-1.amazonaws.com/pp-monthly-update-new-version.csv
"""
import httpx
import aiosqlite
import os
import logging

logger = logging.getLogger(__name__)

DB_FILE = os.getenv("DB_FILE", "northbridge.db")

NE_POSTCODES = [
    "NE1", "NE2", "NE3", "NE4", "NE5", "NE6", "NE7", "NE8", "NE9", "NE10",
    "NE11", "NE12", "NE13", "NE15", "NE16", "NE17", "NE18", "NE20", "NE21",
    "NE22", "NE23", "NE24", "NE25", "NE26", "NE27", "NE28", "NE29", "NE30",
    "NE31", "NE32", "NE33", "NE34", "NE35", "NE36", "NE37", "NE38", "NE39",
    "NE40", "NE41", "NE42", "NE43", "NE44", "NE45", "NE46", "NE47", "NE48",
    "NE61", "NE62", "NE63", "NE64", "NE65", "NE66", "NE67", "NE68", "NE69",
    "NE70", "NE71",
    "SR1", "SR2", "SR3", "SR4", "SR5", "SR6", "SR7", "SR8",
    "DH1", "DH2", "DH3", "DH4", "DH5", "DH6", "DH7", "DH8", "DH9",
    "TS1", "TS2", "TS3", "TS4", "TS5", "TS6", "TS7", "TS8", "TS9", "TS10",
    "TS11", "TS12", "TS13", "TS14", "TS15", "TS16", "TS17", "TS18", "TS19",
    "TS20", "TS21", "TS22", "TS23", "TS24", "TS25", "TS26", "TS27",
    "DL1", "DL2", "DL3", "DL4", "DL5", "DL16", "DL17",
]

SPARQL_ENDPOINT = "https://landregistry.data.gov.uk/landregistry/query"

async def fetch_recent_sales(postcode_prefix: str, limit: int = 100) -> list[dict]:
    """Fetch recent sales from Land Registry SPARQL endpoint for a postcode prefix."""
    query = f"""
    PREFIX lrppi: <http://landregistry.data.gov.uk/def/ppi/>
    PREFIX lrcommon: <http://landregistry.data.gov.uk/def/common/>
    PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

    SELECT ?transactionId ?price ?date ?postcode ?propertyType ?newBuild ?estateType
           ?paon ?saon ?street ?locality ?town ?district ?county
    WHERE {{
        ?transaction lrppi:pricePaid ?price ;
                     lrppi:transactionDate ?date ;
                     lrppi:propertyType ?propertyType ;
                     lrppi:newBuild ?newBuild ;
                     lrppi:estateType ?estateType ;
                     lrppi:transactionId ?transactionId ;
                     lrppi:propertyAddress ?addr .
        ?addr lrcommon:postcode ?postcode .
        OPTIONAL {{ ?addr lrcommon:paon ?paon }}
        OPTIONAL {{ ?addr lrcommon:saon ?saon }}
        OPTIONAL {{ ?addr lrcommon:street ?street }}
        OPTIONAL {{ ?addr lrcommon:locality ?locality }}
        OPTIONAL {{ ?addr lrcommon:town ?town }}
        OPTIONAL {{ ?addr lrcommon:district ?district }}
        OPTIONAL {{ ?addr lrcommon:county ?county }}
        FILTER(STRSTARTS(?postcode, "{postcode_prefix}"))
        FILTER(?date >= "{get_date_12m_ago()}"^^xsd:date)
    }}
    ORDER BY DESC(?date)
    LIMIT {limit}
    """
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                SPARQL_ENDPOINT,
                params={"query": query, "output": "json"},
                headers={"Accept": "application/sparql-results+json"}
            )
            resp.raise_for_status()
            data = resp.json()
            results = []
            for binding in data.get("results", {}).get("bindings", []):
                parts = []
                for field in ["paon", "saon", "street", "locality", "town"]:
                    val = binding.get(field, {}).get("value", "")
                    if val:
                        parts.append(val)
                address = ", ".join(parts)
                results.append({
                    "transaction_id": binding.get("transactionId", {}).get("value", ""),
                    "price": int(float(binding.get("price", {}).get("value", 0))),
                    "date": binding.get("date", {}).get("value", ""),
                    "postcode": binding.get("postcode", {}).get("value", ""),
                    "property_type": _map_property_type(binding.get("propertyType", {}).get("value", "")),
                    "new_build": binding.get("newBuild", {}).get("value", "N"),
                    "estate_type": binding.get("estateType", {}).get("value", ""),
                    "address": address,
                    "district": binding.get("district", {}).get("value", ""),
                    "county": binding.get("county", {}).get("value", ""),
                })
            return results
    except Exception as e:
        logger.error(f"Land Registry fetch failed for {postcode_prefix}: {e}")
        return []

async def import_sales_to_db(postcode_prefix: str):
    """Fetch and store sales data for a postcode prefix."""
    sales = await fetch_recent_sales(postcode_prefix, limit=200)
    if not sales:
        return 0
    async with aiosqlite.connect(DB_FILE) as db:
        imported = 0
        for s in sales:
            try:
                await db.execute(
                    """INSERT OR IGNORE INTO land_registry
                       (transaction_id, price, date, postcode, property_type, new_build, estate_type, address, district, county)
                       VALUES (?,?,?,?,?,?,?,?,?,?)""",
                    (s["transaction_id"], s["price"], s["date"], s["postcode"],
                     s["property_type"], s["new_build"], s["estate_type"],
                     s["address"], s["district"], s["county"])
                )
                imported += 1
            except Exception as e:
                logger.warning(f"Skip duplicate: {e}")
        await db.commit()
    return imported

async def get_comparables(postcode: str, property_type: str = None, months: int = 12) -> dict:
    """Get comparable sales for a postcode area to calculate market value."""
    postcode_prefix = postcode.split(" ")[0] if " " in postcode else postcode[:4]
    async with aiosqlite.connect(DB_FILE) as db:
        db.row_factory = aiosqlite.Row
        query = """
            SELECT price, date, property_type, address, postcode
            FROM land_registry
            WHERE postcode LIKE ?
            AND date >= date('now', '-{} months')
        """.format(months)
        params = [f"{postcode_prefix}%"]
        if property_type:
            query += " AND property_type = ?"
            params.append(property_type)
        query += " ORDER BY date DESC LIMIT 50"
        cursor = await db.execute(query, params)
        rows = await cursor.fetchall()
        if not rows:
            return {"avg": None, "count": 0, "min": None, "max": None, "sales": []}
        prices = [r["price"] for r in rows]
        return {
            "avg": int(sum(prices) / len(prices)),
            "count": len(prices),
            "min": min(prices),
            "max": max(prices),
            "median": sorted(prices)[len(prices) // 2],
            "sales": [dict(r) for r in rows[:10]],
        }

def _map_property_type(uri: str) -> str:
    mapping = {
        "detached": "D", "semi-detached": "S", "terraced": "T",
        "flat-maisonette": "F", "other": "O"
    }
    for k, v in mapping.items():
        if k in uri.lower():
            return v
    return "O"

def get_date_12m_ago() -> str:
    from datetime import datetime, timedelta
    return (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
