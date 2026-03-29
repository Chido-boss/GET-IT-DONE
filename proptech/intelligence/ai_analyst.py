"""
AI deal analyst — uses Claude API to provide natural language deal analysis.
"""
import os
import httpx
import json
import logging

logger = logging.getLogger(__name__)

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
CLAUDE_MODEL = "claude-sonnet-4-6"

SYSTEM_PROMPT = """You are a sharp, experienced property investment analyst specialising in
the North East of England — covering Newcastle, Gateshead, Sunderland, Durham, Teesside,
Northumberland and surrounding areas.

You have deep knowledge of:
- Below market value (BMV) residential deals
- HMO licensing and demand in NE university cities
- Commercial-to-residential conversions via Permitted Development rights
- Planning gain strategies (buying with planning potential, securing permission, selling on)
- Regeneration zone opportunities (Teesworks, Newcastle Quayside, Sunderland Riverside, etc.)
- North East property price benchmarks and rental yields
- Auction strategy and distressed assets

When analysing a deal, you:
1. Give a clear VERDICT: BUY / INVESTIGATE / PASS
2. State the most viable strategy for this specific property
3. Flag any risks
4. Suggest a max offer price
5. Note if the CIC angle applies (regeneration, community benefit)

Be direct, no waffle. Numbers matter more than words."""


async def analyse_deal(property_data: dict, comparables: dict = None, planning_data: dict = None) -> str:
    """Run AI analysis on a property deal."""
    if not ANTHROPIC_API_KEY:
        return "AI analysis unavailable — set ANTHROPIC_API_KEY in .env"

    context_parts = [f"Property: {property_data.get('address', 'Unknown')}"]

    if property_data.get("asking_price"):
        context_parts.append(f"Asking price: £{property_data['asking_price']:,}")

    if property_data.get("property_type"):
        context_parts.append(f"Type: {property_data['property_type']}")

    if property_data.get("bedrooms"):
        context_parts.append(f"Bedrooms: {property_data['bedrooms']}")

    if comparables and comparables.get("avg"):
        context_parts.append(f"Market average (Land Registry): £{comparables['avg']:,} ({comparables['count']} comparable sales)")
        if comparables.get("median"):
            context_parts.append(f"Median sold price: £{comparables['median']:,}")

    if property_data.get("description"):
        context_parts.append(f"Listing description: {property_data['description'][:500]}")

    if property_data.get("days_on_market"):
        context_parts.append(f"Days on market: {property_data['days_on_market']}")

    if planning_data:
        context_parts.append(f"Nearby planning applications: {json.dumps(planning_data, indent=2)[:300]}")

    if property_data.get("bmv_score"):
        context_parts.append(f"System BMV score: {property_data['bmv_score']:.0f}/100")

    prompt = "\n".join(context_parts)
    prompt += "\n\nProvide a concise investment analysis. Include: VERDICT, best strategy, max offer, key risks, and potential profit range."

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": ANTHROPIC_API_KEY,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": CLAUDE_MODEL,
                    "max_tokens": 600,
                    "system": SYSTEM_PROMPT,
                    "messages": [{"role": "user", "content": prompt}],
                }
            )
            resp.raise_for_status()
            data = resp.json()
            return data["content"][0]["text"]
    except Exception as e:
        logger.error(f"AI analysis failed: {e}")
        return f"Analysis unavailable: {e}"


async def score_planning_opportunity(application: dict) -> str:
    """AI analysis of a planning application as an investment opportunity."""
    if not ANTHROPIC_API_KEY:
        return "AI analysis unavailable — set ANTHROPIC_API_KEY in .env"

    prompt = f"""Planning application in {application.get('council', 'NE England')}:

Reference: {application.get('reference', '')}
Address: {application.get('address', '')}
Type: {application.get('application_type', '')}
Description: {application.get('description', '')[:400]}
System uplift score: {application.get('uplift_score', 0):.0f}/100
Opportunity type: {application.get('opportunity_type', '')}

As a NE property investor, analyse this planning application:
1. Does this create a nearby investment opportunity?
2. Should I buy property near this development before it's approved?
3. Is there a direct play (e.g. buy the site if it comes to market)?
4. What's the likely impact on surrounding property values?

Be direct and specific. 3-4 sentences max."""

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": ANTHROPIC_API_KEY,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": CLAUDE_MODEL,
                    "max_tokens": 300,
                    "system": SYSTEM_PROMPT,
                    "messages": [{"role": "user", "content": prompt}],
                }
            )
            resp.raise_for_status()
            data = resp.json()
            return data["content"][0]["text"]
    except Exception as e:
        logger.error(f"Planning AI analysis failed: {e}")
        return f"Analysis unavailable: {e}"
