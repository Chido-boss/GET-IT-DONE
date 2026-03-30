"""
Keyword parser — extracts structured signals from listing text.
"""
import re
from dataclasses import dataclass, field

DISTRESS_TERMS = [
    "chain free", "no chain", "vacant possession", "sold as seen",
    "motivated seller", "quick sale", "cash buyers only", "cash buyer preferred",
    "cash buyer", "requires modernisation", "in need of modernisation",
    "refurbishment opportunity", "refurbishment required", "needs updating",
    "development opportunity", "investment opportunity", "priced to sell",
    "price reduction", "reduced", "price drop", "below market",
    "executor sale", "probate", "repossession", "possession order",
    "as seen", "sold as is", "buyer beware",
]

CONVERSION_TERMS = [
    "change of use", "conversion opportunity", "prior approval",
    "permitted development", "class ma", "class e",
    "office to residential", "commercial to residential",
    "barn conversion", "agricultural building",
    "former", "ex-", "previously used as",
]

PLANNING_POSITIVE_TERMS = [
    "planning permission", "planning granted", "outline planning",
    "full planning", "planning approved", "planning consent",
    "lapsed planning", "planning potential", "development potential",
    "planning uplift",
]

INVESTOR_TERMS = [
    "hmo", "house in multiple occupation", "buy to let", "btl",
    "rental income", "tenanted", "currently let", "investment property",
    "yields", "gross yield", "net yield", "sitting tenant",
    "assured shorthold", "ast",
]

BMV_TERMS = [
    "below market value", "bmv", "below asking", "below valuation",
    "guide price", "offers in the region of", "oiro", "o/a",
    "offers around", "auction guide",
]


@dataclass
class ParsedKeywords:
    distress_hits: list[str] = field(default_factory=list)
    conversion_hits: list[str] = field(default_factory=list)
    planning_hits: list[str] = field(default_factory=list)
    investor_hits: list[str] = field(default_factory=list)
    bmv_hits: list[str] = field(default_factory=list)
    distress_score: float = 0.0
    conversion_score: float = 0.0


def parse_keywords(title: str = "", description: str = "") -> ParsedKeywords:
    """Extract all structured signals from listing text."""
    text = f"{title} {description}".lower()
    # Normalise whitespace
    text = re.sub(r'\s+', ' ', text)

    result = ParsedKeywords()

    result.distress_hits = [t for t in DISTRESS_TERMS if t in text]
    result.conversion_hits = [t for t in CONVERSION_TERMS if t in text]
    result.planning_hits = [t for t in PLANNING_POSITIVE_TERMS if t in text]
    result.investor_hits = [t for t in INVESTOR_TERMS if t in text]
    result.bmv_hits = [t for t in BMV_TERMS if t in text]

    # Weighted distress score
    high_weight = {"chain free", "no chain", "motivated seller", "cash buyers only",
                   "repossession", "probate", "executor sale", "vacant possession"}
    score = 0.0
    for hit in result.distress_hits:
        score += 15.0 if hit in high_weight else 8.0
    result.distress_score = min(score, 100.0)

    # Conversion score
    result.conversion_score = min(len(result.conversion_hits) * 25.0, 100.0)

    return result


def extract_price_from_text(text: str) -> int | None:
    """Pull a price figure from free text if present."""
    patterns = [
        r'£([\d,]+)',
        r'(\d[\d,]+)\s*(?:pcm|per\s+month|pounds)',
    ]
    for pat in patterns:
        m = re.search(pat, text.lower())
        if m:
            try:
                return int(m.group(1).replace(',', ''))
            except ValueError:
                continue
    return None
