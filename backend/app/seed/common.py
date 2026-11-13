"""Shared helpers for the seed modules (no owner-specific data).
"""
from __future__ import annotations

import math
import unicodedata


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def strip_diacritics(text: str) -> str:
    """'Calea Circumvalațiunii' -> 'Calea Circumvalatiunii' (PMT ...FaraDiacritice rule)."""
    text = text.replace("ș", "s").replace("Ș", "S").replace("ş", "s").replace("Ş", "S")
    text = text.replace("ț", "t").replace("Ț", "T").replace("ţ", "t").replace("Ţ", "T")
    norm = unicodedata.normalize("NFKD", text)
    return "".join(c for c in norm if not unicodedata.combining(c))


def haversine_m(a: tuple[float, float], b: tuple[float, float]) -> float:
    lng1, lat1 = map(math.radians, a)
    lng2, lat2 = map(math.radians, b)
    dlat, dlng = lat2 - lat1, lng2 - lng1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng / 2) ** 2
    return 2 * 6_371_000 * math.asin(math.sqrt(h))
