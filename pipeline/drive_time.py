"""
pipeline/drive_time.py
Drive-time estimation for CT towns.

Uses haversine distance × road factor — a deliberate simplification that
keeps the pipeline fully reproducible from public data with no external API.
Accurate enough for band assignment and relative ranking.

Road factor and speed are configurable for sensitivity analysis.

Serves: all anchor scoring, Post #5 (Commuter Arbitrage)
"""

from __future__ import annotations

import math

import pandas as pd

# Straight-line to road-distance multiplier.
# Calibrated so 90 min ≈ ~120 km straight-line (Fairfield County → Hartford).
ROAD_FACTOR = 1.35
AVG_SPEED_KM_MIN = 1.1  # ~66 km/h, mix of highway + local


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Straight-line distance in km between two lat/lon points."""
    if any(math.isnan(x) for x in [lat1, lon1, lat2, lon2]):
        return float("nan")
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def estimate_drive_time(
    anchor_lat: float,
    anchor_lon: float,
    town_lat: float,
    town_lon: float,
    road_factor: float = ROAD_FACTOR,
    avg_speed_km_min: float = AVG_SPEED_KM_MIN,
) -> float:
    """Estimated drive time in minutes from anchor to a town centroid."""
    km = haversine_km(anchor_lat, anchor_lon, town_lat, town_lon)
    return round(km * road_factor / avg_speed_km_min, 1)


def assign_drive_band(
    drive_time_min: float,
    day_tripper_max: int = 90,
    weekender_max: int = 180,
) -> str:
    if math.isnan(drive_time_min):
        return "Unknown"
    if drive_time_min <= day_tripper_max:
        return "Day-Tripper"
    if drive_time_min <= weekender_max:
        return "Weekender"
    return "Beyond"


def add_drive_columns(
    df: pd.DataFrame,
    anchor_lat: float,
    anchor_lon: float,
    day_tripper_max: int = 90,
    weekender_max: int = 180,
) -> pd.DataFrame:
    """
    Add drive_time_min and drive_band columns to a towns DataFrame.

    Expects either town_lat/town_lon columns already present, or falls back
    to the built-in CT town centroid lookup table.
    """
    df = df.copy()

    if "town_lat" not in df.columns or "town_lon" not in df.columns:
        centroids = ct_town_centroids()
        df = df.merge(centroids, on="town", how="left")

    df["drive_time_min"] = df.apply(
        lambda row: estimate_drive_time(
            anchor_lat, anchor_lon,
            row.get("town_lat", float("nan")),
            row.get("town_lon", float("nan")),
        ),
        axis=1,
    )
    df["drive_band"] = df["drive_time_min"].apply(
        lambda t: assign_drive_band(t, day_tripper_max, weekender_max)
    )
    return df


def ct_town_centroids() -> pd.DataFrame:
    """
    Approximate centroids for all 169 CT towns.
    Sourced from Census TIGER data (geographic center / town hall location).
    """
    # fmt: off
    data = [
        ("Andover", 41.7376, -72.3718), ("Ansonia", 41.3443, -73.0779), ("Ashford", 41.8751, -72.1407),
        ("Avon", 41.8084, -72.8315), ("Barkhamsted", 41.9848, -72.9787), ("Beacon Falls", 41.4404, -73.0607),
        ("Berlin", 41.6212, -72.7457), ("Bethany", 41.4390, -72.9968), ("Bethel", 41.3709, -73.4140),
        ("Bethlehem", 41.6376, -73.2115), ("Bloomfield", 41.8301, -72.7293), ("Bolton", 41.7701, -72.4332),
        ("Bozrah", 41.5476, -72.1679), ("Branford", 41.2793, -72.8154), ("Bridgeport", 41.1865, -73.1952),
        ("Bridgewater", 41.5348, -73.3618), ("Bristol", 41.6718, -72.9493), ("Brookfield", 41.4640, -73.4065),
        ("Brooklyn", 41.7882, -71.9480), ("Burlington", 41.7751, -72.9637), ("Canaan", 42.0262, -73.3290),
        ("Canterbury", 41.6987, -71.9757), ("Canton", 41.8612, -72.9004), ("Chaplin", 41.7987, -72.1146),
        ("Cheshire", 41.4990, -72.9007), ("Chester", 41.4026, -72.4499), ("Clinton", 41.2793, -72.5279),
        ("Colchester", 41.5751, -72.3318), ("Colebrook", 42.0112, -73.0932), ("Columbia", 41.6987, -72.2857),
        ("Cornwall", 41.8376, -73.3290), ("Coventry", 41.7848, -72.3501), ("Cromwell", 41.5959, -72.6490),
        ("Danbury", 41.3948, -73.4540), ("Darien", 41.0793, -73.4687), ("Deep River", 41.3818, -72.4393),
        ("Derby", 41.3248, -73.0874), ("Durham", 41.4859, -72.6829), ("East Granby", 41.9501, -72.7329),
        ("East Haddam", 41.4651, -72.4607), ("East Hampton", 41.5776, -72.5029), ("East Hartford", 41.7826, -72.6126),
        ("East Haven", 41.2762, -72.8682), ("East Lyme", 41.3737, -72.2265), ("East Windsor", 41.9112, -72.6140),
        ("Eastford", 41.8951, -72.0696), ("Easton", 41.2537, -73.3015), ("Ellington", 41.9001, -72.4668),
        ("Enfield", 41.9762, -72.5923), ("Essex", 41.3526, -72.3951), ("Fairfield", 41.1415, -73.2637),
        ("Farmington", 41.7190, -72.8329), ("Franklin", 41.6151, -72.1621), ("Glastonbury", 41.7026, -72.6073),
        ("Goshen", 41.8487, -73.2271), ("Granby", 41.9626, -72.8457), ("Greenwich", 41.0534, -73.6282),
        ("Griswold", 41.5859, -71.9571), ("Groton", 41.3501, -72.0793), ("Guilford", 41.2887, -72.6818),
        ("Haddam", 41.4776, -72.5026), ("Hamden", 41.3959, -72.8979), ("Hampton", 41.7848, -72.0601),
        ("Hartford", 41.7658, -72.6734), ("Hartland", 42.0012, -72.9679), ("Harwinton", 41.7637, -73.0596),
        ("Hebron", 41.6626, -72.3668), ("Kent", 41.7262, -73.4793), ("Killingly", 41.8373, -71.8743),
        ("Killingworth", 41.3637, -72.5746), ("Lebanon", 41.6401, -72.2251), ("Ledyard", 41.4387, -72.0143),
        ("Lisbon", 41.5987, -72.0126), ("Litchfield", 41.7487, -73.1882), ("Lyme", 41.3776, -72.3293),
        ("Madison", 41.2790, -72.5985), ("Manchester", 41.7759, -72.5215), ("Mansfield", 41.7701, -72.2307),
        ("Marlborough", 41.6387, -72.4554), ("Meriden", 41.5376, -72.8068), ("Middlebury", 41.5387, -73.1357),
        ("Middlefield", 41.5076, -72.7065), ("Middletown", 41.5623, -72.6506), ("Milford", 41.2223, -73.0568),
        ("Monroe", 41.3373, -73.2093), ("Montville", 41.4701, -72.1468), ("Morris", 41.6876, -73.1918),
        ("Naugatuck", 41.4887, -73.0513), ("New Britain", 41.6612, -72.7795), ("New Canaan", 41.1468, -73.4951),
        ("New Fairfield", 41.4762, -73.4882), ("New Hartford", 41.8751, -72.9732), ("New Haven", 41.3082, -72.9251),
        ("New London", 41.3551, -72.0996), ("New Milford", 41.5776, -73.4082), ("Newtown", 41.4137, -73.3093),
        ("Newington", 41.6951, -72.7232), ("Norfolk", 42.0276, -73.1979), ("North Branford", 41.3226, -72.7679),
        ("North Canaan", 42.0251, -73.3407), ("North Haven", 41.3887, -72.8582), ("North Stonington", 41.4437, -71.8807),
        ("Norwalk", 41.1176, -73.4082), ("Norwich", 41.5237, -72.0757), ("Old Lyme", 41.3151, -72.3293),
        ("Old Saybrook", 41.2951, -72.3757), ("Orange", 41.2787, -73.0257), ("Oxford", 41.4337, -73.1182),
        ("Plainfield", 41.6787, -71.9143), ("Plainville", 41.6737, -72.8593), ("Plymouth", 41.6737, -73.0543),
        ("Pomfret", 41.8837, -71.9657), ("Portland", 41.5787, -72.6379), ("Preston", 41.5087, -71.9657),
        ("Prospect", 41.5037, -72.9743), ("Putnam", 41.9087, -71.9093), ("Redding", 41.3037, -73.3882),
        ("Ridgefield", 41.2837, -73.4982), ("Rocky Hill", 41.6651, -72.6429), ("Roxbury", 41.5537, -73.3043),
        ("Salem", 41.4887, -72.2768), ("Salisbury", 41.9851, -73.4243), ("Scotland", 41.6987, -72.0807),
        ("Seymour", 41.3987, -73.0757), ("Sharon", 41.8837, -73.4793), ("Shelton", 41.3162, -73.0882),
        ("Sherman", 41.5837, -73.4943), ("Simsbury", 41.8787, -72.8093), ("Somers", 41.9987, -72.4468),
        ("South Windsor", 41.8312, -72.5829), ("Southbury", 41.4812, -73.2193), ("Southington", 41.5987, -72.8793),
        ("Sprague", 41.6187, -71.9993), ("Stafford", 41.9887, -72.3068), ("Stamford", 41.0534, -73.5387),
        ("Sterling", 41.7087, -71.8357), ("Stonington", 41.3337, -71.9043), ("Stratford", 41.1848, -73.1332),
        ("Suffield", 41.9837, -72.6543), ("Thomaston", 41.6737, -73.0743), ("Thompson", 41.9437, -71.8657),
        ("Tolland", 41.8737, -72.3668), ("Torrington", 41.8007, -73.1232), ("Trumbull", 41.2437, -73.2007),
        ("Union", 41.9937, -72.1593), ("Vernon", 41.8337, -72.4632), ("Voluntown", 41.5737, -71.8593),
        ("Wallingford", 41.4570, -72.8232), ("Warren", 41.7437, -73.3643), ("Washington", 41.6337, -73.3143),
        ("Waterbury", 41.5582, -73.0515), ("Waterford", 41.3737, -72.1443), ("Watertown", 41.6037, -73.1182),
        ("West Hartford", 41.7626, -72.7382), ("West Haven", 41.2709, -72.9471), ("Westbrook", 41.2937, -72.4543),
        ("Weston", 41.2037, -73.3793), ("Westport", 41.1415, -73.3582), ("Wethersfield", 41.7126, -72.6582),
        ("Willington", 41.8887, -72.2607), ("Wilton", 41.1937, -73.4382), ("Winchester", 41.9437, -73.0632),
        ("Windham", 41.7037, -72.1557), ("Windsor", 41.8526, -72.6432), ("Windsor Locks", 41.9287, -72.6282),
        ("Wolcott", 41.5987, -72.9743), ("Woodbridge", 41.3537, -73.0082), ("Woodbury", 41.5437, -73.2093),
        ("Woodstock", 41.9637, -71.9793),
    ]
    # fmt: on
    return pd.DataFrame(data, columns=["town", "town_lat", "town_lon"])
