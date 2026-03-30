"""
Haversine distance calculation for property-to-zone matching.
"""
import math
from dataclasses import dataclass


@dataclass
class DistanceResult:
    distance_km: float
    distance_miles: float
    within_zone: bool


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Calculate great-circle distance between two coordinates in km."""
    R = 6371.0  # Earth radius in km
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def calculate_distance(
    lat1: float | None,
    lng1: float | None,
    lat2: float | None,
    lng2: float | None,
    zone_radius_km: float = 1.0,
) -> DistanceResult | None:
    """
    Calculate distance between a listing and a zone center.
    Returns None if coordinates are missing.
    """
    if any(v is None for v in [lat1, lng1, lat2, lng2]):
        return None
    dist_km = haversine_km(lat1, lng1, lat2, lng2)
    return DistanceResult(
        distance_km=round(dist_km, 3),
        distance_miles=round(dist_km * 0.621371, 3),
        within_zone=dist_km <= zone_radius_km,
    )


def postcode_to_approximate_coords(postcode: str) -> tuple[float, float] | None:
    """
    Rough postcode-to-coordinate lookup for NE postcodes.
    In production, use OS Code-Point Open or Postcodes.io API.
    This covers the main NE postcode districts.
    """
    # Approximate centroids for NE postcode districts
    NE_APPROX = {
        "NE1": (54.9738, -1.6142), "NE2": (54.9801, -1.6035), "NE3": (55.0043, -1.6198),
        "NE4": (54.9720, -1.6380), "NE5": (54.9895, -1.6798), "NE6": (54.9793, -1.5712),
        "NE7": (54.9951, -1.5783), "NE8": (54.9594, -1.6015), "NE9": (54.9449, -1.5947),
        "NE10": (54.9500, -1.5500), "NE11": (54.9347, -1.6427), "NE12": (55.0125, -1.5442),
        "NE15": (54.9805, -1.7231), "NE16": (54.9189, -1.7103), "NE21": (54.9386, -1.7584),
        "NE22": (55.1285, -1.6669), "NE23": (55.0843, -1.6169), "NE24": (55.1279, -1.5154),
        "NE25": (55.0453, -1.4695), "NE26": (55.0604, -1.4396), "NE27": (55.0285, -1.5003),
        "NE28": (54.9983, -1.5195), "NE29": (55.0139, -1.4673), "NE30": (55.0213, -1.4358),
        "NE31": (54.9787, -1.5063), "NE32": (54.9606, -1.4780), "NE33": (55.0027, -1.4315),
        "NE34": (54.9852, -1.4210), "NE35": (54.9607, -1.4505), "NE36": (54.9432, -1.4604),
        "NE37": (54.9125, -1.5547), "NE38": (54.8952, -1.5394),
        "SR1": (54.9069, -1.3823), "SR2": (54.8971, -1.3937), "SR3": (54.8784, -1.4091),
        "SR4": (54.8963, -1.4123), "SR5": (54.9154, -1.4268), "SR6": (54.9308, -1.3596),
        "SR7": (54.8455, -1.3700), "SR8": (54.7875, -1.3235),
        "DH1": (54.7761, -1.5764), "DH2": (54.8525, -1.5957), "DH3": (54.8710, -1.5776),
        "DH4": (54.8490, -1.4975), "DH5": (54.8278, -1.4600), "DH6": (54.7608, -1.4542),
        "DH7": (54.8201, -1.7136), "DH8": (54.8550, -1.8594), "DH9": (54.8808, -1.7291),
        "TS1": (54.5715, -1.2340), "TS2": (54.5852, -1.2234), "TS3": (54.5524, -1.2012),
        "TS4": (54.5512, -1.2512), "TS5": (54.5441, -1.2698), "TS6": (54.5741, -1.1614),
        "TS7": (54.5229, -1.1741), "TS8": (54.5074, -1.2185), "TS9": (54.4757, -1.1337),
        "TS10": (54.5845, -1.0907), "TS11": (54.5885, -1.0450), "TS12": (54.5558, -0.9823),
        "TS13": (54.5490, -0.8679), "TS14": (54.5355, -1.0773), "TS17": (54.5325, -1.3085),
        "TS18": (54.5631, -1.3188), "TS19": (54.5584, -1.3380), "TS20": (54.5984, -1.3115),
        "TS21": (54.5781, -1.5239), "TS23": (54.6143, -1.2695), "TS24": (54.6950, -1.2119),
        "TS25": (54.7033, -1.1842), "TS26": (54.6985, -1.2278), "TS27": (54.7294, -1.2943),
        "DL1": (54.5226, -1.5541), "DL2": (54.4987, -1.6037), "DL3": (54.5192, -1.5787),
    }
    prefix = postcode.strip().upper().split(" ")[0]
    # Try exact match, then strip last char for district
    if prefix in NE_APPROX:
        return NE_APPROX[prefix]
    # Try 3-char prefix
    if prefix[:3] in NE_APPROX:
        return NE_APPROX[prefix[:3]]
    return None
