"""
CSV import parsers for listings, comparables (Land Registry format), and planning applications.
"""

from __future__ import annotations

import csv
import io
from datetime import date, datetime
from typing import Dict, List, Optional


def _safe_int(val: str) -> Optional[int]:
    """Parse integer, returning None on failure."""
    try:
        cleaned = val.strip().replace(",", "").replace("£", "")
        return int(float(cleaned))
    except (ValueError, AttributeError):
        return None


def _safe_float(val: str) -> Optional[float]:
    """Parse float, returning None on failure."""
    try:
        return float(val.strip().replace(",", ""))
    except (ValueError, AttributeError):
        return None


def _safe_date(val: str, formats: List[str] = None) -> Optional[date]:
    """Parse a date string, trying multiple formats."""
    if not val or not val.strip():
        return None
    formats = formats or [
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%Y/%m/%d",
        "%d %b %Y",
        "%d %B %Y",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(val.strip(), fmt).date()
        except ValueError:
            continue
    return None


# ---------------------------------------------------------------------------
# Listings CSV
# ---------------------------------------------------------------------------

LISTINGS_REQUIRED_COLS = {"title", "address", "postcode", "asking_price", "property_type"}

LISTINGS_COLUMN_MAP = {
    # Canonical name -> list of possible CSV header variations
    "source": ["source", "portal", "data_source"],
    "source_id": ["source_id", "id", "listing_id", "ref", "reference"],
    "title": ["title", "property_title", "name", "heading"],
    "address": ["address", "full_address", "property_address"],
    "postcode": ["postcode", "post_code", "postal_code"],
    "council": ["council", "local_authority", "la", "borough"],
    "latitude": ["latitude", "lat"],
    "longitude": ["longitude", "lng", "lon"],
    "property_type": ["property_type", "type", "prop_type"],
    "tenure": ["tenure"],
    "bedrooms": ["bedrooms", "beds", "num_bedrooms"],
    "bathrooms": ["bathrooms", "baths", "num_bathrooms"],
    "asking_price": ["asking_price", "price", "list_price", "listed_price"],
    "previous_price": ["previous_price", "old_price", "prior_price"],
    "date_listed": ["date_listed", "listed_date", "listing_date", "date"],
    "description": ["description", "details", "property_description"],
    "url": ["url", "link", "listing_url", "property_url"],
    "status": ["status"],
    "agent_name": ["agent_name", "agent", "estate_agent"],
    "agent_phone": ["agent_phone", "phone", "tel", "telephone"],
    "days_on_market": ["days_on_market", "dom", "days_listed"],
    "price_reduction_count": ["price_reduction_count", "reductions", "price_reductions"],
}


def _build_col_lookup(headers: List[str], column_map: Dict) -> Dict[str, Optional[str]]:
    """
    Build a mapping from canonical field name -> actual CSV column name.
    """
    headers_lower = {h.lower().strip(): h for h in headers}
    lookup: Dict[str, Optional[str]] = {}
    for canonical, aliases in column_map.items():
        for alias in aliases:
            if alias.lower() in headers_lower:
                lookup[canonical] = headers_lower[alias.lower()]
                break
        else:
            lookup[canonical] = None
    return lookup


def parse_listings_csv(file_content: bytes) -> List[dict]:
    """
    Parse a listings CSV file.

    Required columns (case-insensitive): title, address, postcode, asking_price, property_type
    Returns list of dicts ready for ListingCreate schema.
    """
    text = file_content.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    headers = reader.fieldnames or []

    col = _build_col_lookup(list(headers), LISTINGS_COLUMN_MAP)

    results: List[dict] = []
    errors: List[str] = []

    for row_num, row in enumerate(reader, start=2):
        def get(field: str) -> str:
            csv_col = col.get(field)
            return (row.get(csv_col, "") or "").strip() if csv_col else ""

        # Required fields
        title = get("title")
        address = get("address")
        postcode = get("postcode").upper()
        asking_price_raw = get("asking_price")
        property_type = get("property_type").upper()[:1] if get("property_type") else ""

        if not all([title, address, postcode, asking_price_raw]):
            errors.append(f"Row {row_num}: missing required field(s)")
            continue

        asking_price = _safe_int(asking_price_raw)
        if asking_price is None or asking_price <= 0:
            errors.append(f"Row {row_num}: invalid asking_price '{asking_price_raw}'")
            continue

        # Normalise property type
        pt_map = {
            "DETACHED": "D", "D": "D",
            "SEMI": "S", "SEMI-DETACHED": "S", "S": "S",
            "TERRACED": "T", "TERRACE": "T", "T": "T",
            "FLAT": "F", "APARTMENT": "F", "F": "F",
            "OTHER": "O", "O": "O",
            "COMMERCIAL": "C", "C": "C",
        }
        property_type = pt_map.get(property_type, pt_map.get(get("property_type").upper(), "O"))

        record: dict = {
            "source": get("source") or "csv_import",
            "source_id": get("source_id") or None,
            "title": title,
            "address": address,
            "postcode": postcode,
            "council": get("council") or None,
            "latitude": _safe_float(get("latitude")),
            "longitude": _safe_float(get("longitude")),
            "property_type": property_type,
            "tenure": get("tenure") or None,
            "bedrooms": _safe_int(get("bedrooms")),
            "bathrooms": _safe_int(get("bathrooms")),
            "asking_price": asking_price,
            "previous_price": _safe_int(get("previous_price")),
            "date_listed": _safe_date(get("date_listed")),
            "description": get("description") or None,
            "url": get("url") or None,
            "status": get("status") or "active",
            "agent_name": get("agent_name") or None,
            "agent_phone": get("agent_phone") or None,
            "days_on_market": _safe_int(get("days_on_market")),
            "price_reduction_count": _safe_int(get("price_reduction_count")) or 0,
        }
        results.append(record)

    return results


# ---------------------------------------------------------------------------
# Land Registry Comparables CSV
# ---------------------------------------------------------------------------
# Format: Transaction unique identifier, Price, Date of Transfer, Postcode,
#         Property Type, Old/New, Duration, PAON, SAON, Street, Locality,
#         Town/City, District, County, PPD Category Type, Record Status

LR_COL_TRANSACTION = "Transaction unique identifier"
LR_COL_PRICE = "Price"
LR_COL_DATE = "Date of Transfer"
LR_COL_POSTCODE = "Postcode"
LR_COL_PROP_TYPE = "Property Type"
LR_COL_OLD_NEW = "Old/New"
LR_COL_DURATION = "Duration"
LR_COL_PAON = "PAON"
LR_COL_SAON = "SAON"
LR_COL_STREET = "Street"
LR_COL_LOCALITY = "Locality"
LR_COL_TOWN = "Town/City"
LR_COL_DISTRICT = "District"
LR_COL_COUNTY = "County"
LR_COL_PPD = "PPD Category Type"
LR_COL_STATUS = "Record Status"


def parse_comparables_csv(file_content: bytes) -> List[dict]:
    """
    Parse a Land Registry Price Paid Data CSV.

    Handles both the standard format with headers and the header-free bulk download format.
    Returns list of dicts ready for ComparableSale creation.
    """
    text = file_content.decode("utf-8-sig", errors="replace")

    # Check if the CSV has headers or not (LR bulk files have no header row)
    first_line = text.split("\n")[0]
    if LR_COL_PRICE.lower() in first_line.lower() or "transaction" in first_line.lower():
        reader = csv.DictReader(io.StringIO(text))
        has_headers = True
    else:
        # Headerless bulk format
        fieldnames = [
            LR_COL_TRANSACTION, LR_COL_PRICE, LR_COL_DATE, LR_COL_POSTCODE,
            LR_COL_PROP_TYPE, LR_COL_OLD_NEW, LR_COL_DURATION,
            LR_COL_PAON, LR_COL_SAON, LR_COL_STREET, LR_COL_LOCALITY,
            LR_COL_TOWN, LR_COL_DISTRICT, LR_COL_COUNTY,
            LR_COL_PPD, LR_COL_STATUS,
        ]
        reader = csv.DictReader(io.StringIO(text), fieldnames=fieldnames)
        has_headers = False

    results: List[dict] = []

    for row in reader:
        def g(col: str) -> str:
            val = row.get(col, "") or ""
            return val.strip().strip('"')

        transaction_id = g(LR_COL_TRANSACTION) or None
        price_raw = g(LR_COL_PRICE)
        date_raw = g(LR_COL_DATE)
        postcode = g(LR_COL_POSTCODE).upper()
        prop_type_raw = g(LR_COL_PROP_TYPE).upper()
        old_new = g(LR_COL_OLD_NEW).upper()
        duration = g(LR_COL_DURATION).upper()

        # Build address string
        saon = g(LR_COL_SAON)
        paon = g(LR_COL_PAON)
        street = g(LR_COL_STREET)
        locality = g(LR_COL_LOCALITY)
        town = g(LR_COL_TOWN)
        address_parts = [p for p in [saon, paon, street, locality, town] if p]
        address = ", ".join(address_parts) if address_parts else None

        district = g(LR_COL_DISTRICT) or None
        county = g(LR_COL_COUNTY) or None

        price = _safe_int(price_raw)
        if price is None or price <= 0:
            continue

        sold_date = _safe_date(date_raw, ["%Y-%m-%d %H:%M", "%Y-%m-%d", "%d/%m/%Y"])
        if sold_date is None:
            continue

        if not postcode:
            continue

        # Normalise property type: D=Detached, S=Semi, T=Terraced, F=Flat, O=Other
        prop_type_map = {"D": "D", "S": "S", "T": "T", "F": "F", "O": "O"}
        property_type = prop_type_map.get(prop_type_raw[:1] if prop_type_raw else "O", "O")

        new_build = old_new == "Y"

        # Duration -> estate type: F=Freehold, L=Leasehold
        estate_type = duration[:1] if duration else None

        record: dict = {
            "transaction_id": transaction_id,
            "price": price,
            "date_sold": sold_date,
            "postcode": postcode,
            "property_type": property_type,
            "new_build": new_build,
            "estate_type": estate_type,
            "address": address,
            "district": district,
            "county": county,
            "bedrooms": None,  # Land Registry doesn't include bedrooms
            "source": "land_registry",
        }
        results.append(record)

    return results


# ---------------------------------------------------------------------------
# Planning applications CSV
# ---------------------------------------------------------------------------

PLANNING_COLUMN_MAP = {
    "council": ["council", "local_authority", "la", "lpa"],
    "application_reference": [
        "application_reference", "ref", "reference", "app_ref",
        "application_number", "case_reference",
    ],
    "address": ["address", "site_address", "property_address", "location"],
    "postcode": ["postcode", "post_code"],
    "latitude": ["latitude", "lat"],
    "longitude": ["longitude", "lng", "lon"],
    "application_type": ["application_type", "type", "app_type", "category"],
    "proposal": ["proposal", "description", "development_description", "details"],
    "status": ["status", "app_status", "current_status"],
    "decision": ["decision", "outcome", "result"],
    "date_received": ["date_received", "received_date", "received"],
    "date_validated": ["date_validated", "validated_date", "validated"],
    "date_decided": ["date_decided", "decision_date", "decided", "determination_date"],
    "url": ["url", "link", "application_url"],
}


def _detect_planning_uplift_signals(proposal: str) -> List[str]:
    """
    Scan proposal text for planning uplift signals.
    Returns list of matched signal strings.
    """
    from app.services.scoring import PLANNING_UPLIFT_KEYWORDS

    if not proposal:
        return []

    proposal_lower = proposal.lower()
    found = [kw for kw in PLANNING_UPLIFT_KEYWORDS if kw in proposal_lower]
    return found


def _calculate_planning_uplift_score(signals: List[str]) -> float:
    """Calculate an uplift score (0-10) based on detected signals."""
    if not signals:
        return 0.0
    # High-value signals
    HIGH_VALUE = {"change of use", "conversion", "new dwellings", "new homes", "mixed use"}
    high_count = sum(1 for s in signals if s in HIGH_VALUE)
    base = min(5.0, len(signals) * 1.5)
    bonus = min(5.0, high_count * 2.5)
    return round(min(10.0, base + bonus), 1)


def parse_planning_csv(file_content: bytes) -> List[dict]:
    """
    Parse a planning applications CSV file.

    Required columns: council, application_reference, address
    Returns list of dicts ready for PlanningApplication creation.
    """
    text = file_content.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    headers = reader.fieldnames or []

    col = _build_col_lookup(list(headers), PLANNING_COLUMN_MAP)

    results: List[dict] = []

    for row_num, row in enumerate(reader, start=2):
        def get(field: str) -> str:
            csv_col = col.get(field)
            return (row.get(csv_col, "") or "").strip() if csv_col else ""

        council = get("council")
        application_reference = get("application_reference")
        address = get("address")

        if not all([council, application_reference, address]):
            continue

        proposal = get("proposal") or None
        uplift_signals = _detect_planning_uplift_signals(proposal or "")
        uplift_score = _calculate_planning_uplift_score(uplift_signals)

        record: dict = {
            "council": council,
            "application_reference": application_reference,
            "address": address,
            "postcode": get("postcode").upper() or None,
            "latitude": _safe_float(get("latitude")),
            "longitude": _safe_float(get("longitude")),
            "application_type": get("application_type") or None,
            "proposal": proposal,
            "status": get("status") or None,
            "decision": get("decision") or None,
            "date_received": _safe_date(get("date_received")),
            "date_validated": _safe_date(get("date_validated")),
            "date_decided": _safe_date(get("date_decided")),
            "url": get("url") or None,
            "uplift_signals": uplift_signals if uplift_signals else None,
            "uplift_score": uplift_score,
        }
        results.append(record)

    return results
