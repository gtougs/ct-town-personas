"""
tests/test_drive_time.py
Unit tests for pipeline.drive_time.

Reference drive times sourced from Google Maps (driving, typical conditions,
no traffic), May 2026, from each town centroid to CT Science Center (Hartford).
Tolerance is ±20 min or ±25%, whichever is larger, reflecting the known
limitations of the haversine + piecewise-speed heuristic (see module docstring).

Critical constraint: drive-band classification must match Google Maps for all
reference towns — a band error (Day-Tripper vs Weekender) would misdirect
marketing recommendations.
"""
import math
import pytest
from pipeline.drive_time import estimate_drive_time, assign_drive_band, haversine_km

ANCHOR_LAT = 41.7659  # CT Science Center
ANCHOR_LON = -72.6693

# (town, town_lat, town_lon, google_maps_minutes, expected_band)
REFERENCE_TRIPS = [
    ("West Hartford",  41.7626, -72.7382,  11, "Day-Tripper"),
    ("Glastonbury",    41.7026, -72.6073,  16, "Day-Tripper"),
    ("Simsbury",       41.8787, -72.8093,  27, "Day-Tripper"),
    ("Cheshire",       41.4990, -72.9007,  37, "Day-Tripper"),
    ("Hamden",         41.3959, -72.8979,  43, "Day-Tripper"),
    ("Trumbull",       41.2437, -73.2007,  78, "Day-Tripper"),
    ("Danbury",        41.3948, -73.4540,  80, "Day-Tripper"),
    ("Norwalk",        41.1176, -73.4082,  87, "Day-Tripper"),
    ("Fairfield",      41.1415, -73.2637,  72, "Day-Tripper"),
    ("Greenwich",      41.0534, -73.6282,  96, "Weekender"),
]


@pytest.mark.parametrize("town,lat,lon,google_min,expected_band", REFERENCE_TRIPS)
def test_drive_time_within_tolerance(town, lat, lon, google_min, expected_band):
    model = estimate_drive_time(ANCHOR_LAT, ANCHOR_LON, lat, lon)
    tolerance = max(20, google_min * 0.25)
    assert abs(model - google_min) <= tolerance, (
        f"{town}: model={model:.1f} min, google={google_min} min, "
        f"error={abs(model-google_min):.1f} > tolerance={tolerance:.1f}"
    )


@pytest.mark.parametrize("town,lat,lon,google_min,expected_band", REFERENCE_TRIPS)
def test_drive_band_matches_google(town, lat, lon, google_min, expected_band):
    """Band classification must be correct for all reference towns."""
    model_time = estimate_drive_time(ANCHOR_LAT, ANCHOR_LON, lat, lon)
    model_band = assign_drive_band(model_time)
    assert model_band == expected_band, (
        f"{town}: model band={model_band}, expected={expected_band} "
        f"(model={model_time:.1f} min, google={google_min} min)"
    )


def test_haversine_hartford_new_haven():
    # Hartford ↔ New Haven straight-line is ~55 km; within ±3 km
    d = haversine_km(41.7658, -72.6734, 41.3082, -72.9251)
    assert 52 <= d <= 58, f"Expected ~55 km, got {d:.1f}"


def test_nan_inputs_return_nan():
    result = estimate_drive_time(ANCHOR_LAT, ANCHOR_LON, float("nan"), -72.7)
    assert math.isnan(result)


def test_zero_distance():
    result = estimate_drive_time(ANCHOR_LAT, ANCHOR_LON, ANCHOR_LAT, ANCHOR_LON)
    assert result == 0.0


def test_assign_drive_band_boundaries():
    assert assign_drive_band(0) == "Day-Tripper"
    assert assign_drive_band(90) == "Day-Tripper"
    assert assign_drive_band(90.1) == "Weekender"
    assert assign_drive_band(180) == "Weekender"
    assert assign_drive_band(180.1) == "Beyond"
