"""Demand seed: OD centroids, land-use mix, trip rates and the 12 OD pairs.

OWNER: Lucas (demand & calibration). Consumed only through engine.demand_model.build_od().
"""
from __future__ import annotations

from typing import Any


# ---------------------------------------------------------------------------
# OD centroids + land-use mix (for land-use driven demand generation, §9.2)
# ---------------------------------------------------------------------------

CENTROID_LAND_USE: dict[str, dict[str, float]] = {
    # residential, office, school (incl. university), retail, leisure  — relative floor-area weights
    "N_SOARELUI": {"residential": 0.75, "office": 0.05, "school": 0.10, "retail": 0.05, "leisure": 0.05},
    "N_CONTINENTAL": {"residential": 0.15, "office": 0.45, "school": 0.05, "retail": 0.20, "leisure": 0.15},
    "N_DOJA": {"residential": 0.55, "office": 0.15, "school": 0.10, "retail": 0.15, "leisure": 0.05},
    "N_TRAIAN": {"residential": 0.30, "office": 0.35, "school": 0.10, "retail": 0.15, "leisure": 0.10},
    "N_DACIA": {"residential": 0.80, "office": 0.05, "school": 0.05, "retail": 0.08, "leisure": 0.02},
    "N_PIATA_700": {"residential": 0.10, "office": 0.35, "school": 0.10, "retail": 0.20, "leisure": 0.25},
    "N_FRATELIA": {"residential": 0.75, "office": 0.05, "school": 0.08, "retail": 0.10, "leisure": 0.02},
    "N_CATEDRALA": {"residential": 0.10, "office": 0.35, "school": 0.15, "retail": 0.15, "leisure": 0.25},
    "N_LUGOJULUI": {"residential": 0.60, "office": 0.15, "school": 0.05, "retail": 0.15, "leisure": 0.05},
    "N_OPERA": {"residential": 0.05, "office": 0.40, "school": 0.05, "retail": 0.25, "leisure": 0.25},
    "N_ARADULUI_N": {"residential": 0.60, "office": 0.15, "school": 0.05, "retail": 0.15, "leisure": 0.05},
    "N_COMPLEX": {"residential": 0.20, "office": 0.10, "school": 0.55, "retail": 0.05, "leisure": 0.10},
}


# Trip rates by land use (production P, attraction A) per demand profile.
TRIP_RATES: dict[str, dict[str, dict[str, float]]] = {
    "morning_rush": {
        "P": {"residential": 1.00, "office": 0.15, "school": 0.20, "retail": 0.20, "leisure": 0.10},
        "A": {"residential": 0.20, "office": 1.00, "school": 1.00, "retail": 0.30, "leisure": 0.10},
    },
    "evening_rush": {
        "P": {"residential": 0.35, "office": 1.00, "school": 0.80, "retail": 0.60, "leisure": 0.40},
        "A": {"residential": 1.00, "office": 0.20, "school": 0.15, "retail": 0.50, "leisure": 0.40},
    },
    "weekend": {
        "P": {"residential": 0.60, "office": 0.10, "school": 0.10, "retail": 0.80, "leisure": 0.70},
        "A": {"residential": 0.50, "office": 0.10, "school": 0.10, "retail": 1.00, "leisure": 0.90},
    },
    "event_rush": {
        "P": {"residential": 0.75, "office": 0.40, "school": 0.30, "retail": 0.50, "leisure": 0.60},
        "A": {"residential": 0.30, "office": 0.30, "school": 0.20, "retail": 0.50, "leisure": 1.00},
    },
}


# Overall demand level (relative to the morning peak hour) per profile.
PROFILE_LEVEL = {"morning_rush": 1.0, "evening_rush": 1.0, "weekend": 0.62, "event_rush": 0.95}


# 12 OD pairs: 6 radial corridors in both directions. ``base`` is the calibrated
# morning-rush inbound demand of the corridor (veh/h); outbound and other profiles
# follow from the land-use gravity model in engine/demand_model.py.
# ``paths`` are the curated candidate route sets P^k (node sequences), as in Burov et al.
OD_PAIRS: list[dict[str, Any]] = [
    {"id": "OD01", "corridor": "C1", "inbound": True, "origin": "N_SOARELUI", "destination": "N_CONTINENTAL",
     "label": "Calea Martirilor → Cetate", "base": 1600, "paths": [
         ["N_SOARELUI", "N_MARTIRILOR_S", "N_CLUJ_S", "N_COMPLEX", "N_MV_E", "N_DECEBAL", "N_CONTINENTAL"],
         ["N_SOARELUI", "N_MARTIRILOR_S", "N_CLUJ_S", "N_MV_EROILOR", "N_BRATIANU", "N_CONTINENTAL"],
         ["N_SOARELUI", "N_MARTIRILOR_S", "N_REBREANU", "N_PARC_JUSTITIEI", "N_MV_EROILOR", "N_BRATIANU", "N_CONTINENTAL"],
     ]},
    {"id": "OD02", "corridor": "C2", "inbound": True, "origin": "N_DOJA", "destination": "N_TRAIAN",
     "label": "Elisabetin (Piața Doina) → Fabric", "base": 1700, "paths": [
         ["N_DOJA", "N_MV_W", "N_CATEDRALA", "N_OPERA", "N_BASTION", "N_ROMANILOR", "N_TRAIAN"],
         ["N_DOJA", "N_MV_W", "N_CATEDRALA", "N_CONTINENTAL", "N_DECEBAL", "N_3AUG_MID", "N_TRAIAN"],
         ["N_DOJA", "N_MV_W", "N_MV_EROILOR", "N_MV_E", "N_DECEBAL", "N_3AUG_MID", "N_TRAIAN"],
     ]},
    {"id": "OD03", "corridor": "C3", "inbound": True, "origin": "N_DACIA", "destination": "N_PIATA_700",
     "label": "Dacia / Circumvalațiunii → Cetate (Piața 700)", "base": 1850, "paths": [
         ["N_DACIA", "N_CIRC_DACIA_MID", "N_CIRC_N", "N_IULIUS", "N_UNIRII", "N_PIATA_700"],
         ["N_DACIA", "N_CIRC_DACIA_MID", "N_CIRC_N", "N_LAZAR_W", "N_LAZAR_E", "N_PIATA_700"],
         ["N_DACIA", "N_TORONTAL", "N_CIRC_W", "N_LAZAR_W", "N_LAZAR_E", "N_PIATA_700"],
     ]},
    {"id": "OD04", "corridor": "C4", "inbound": True, "origin": "N_FRATELIA", "destination": "N_CATEDRALA",
     "label": "Calea Șagului → Catedrală", "base": 1700, "paths": [
         ["N_FRATELIA", "N_SAGULUI", "N_IOSEFIN", "N_GARA", "N_DRAGALINA", "N_CATEDRALA"],
         ["N_FRATELIA", "N_SAGULUI", "N_IOSEFIN", "N_MARIA", "N_CAROL_MID", "N_CATEDRALA"],
         ["N_FRATELIA", "N_SAGULUI", "N_MOCIONI", "N_MARIA", "N_CAROL_MID", "N_CATEDRALA"],
     ]},
    {"id": "OD05", "corridor": "C5", "inbound": True, "origin": "N_LUGOJULUI", "destination": "N_OPERA",
     "label": "Calea Lugojului → Operă", "base": 1100, "paths": [
         ["N_LUGOJULUI", "N_TRAIAN", "N_ROMANILOR", "N_BASTION", "N_OPERA"],
         ["N_LUGOJULUI", "N_TRAIAN", "N_3AUG_MID", "N_DECEBAL", "N_CONTINENTAL", "N_CATEDRALA", "N_OPERA"],
     ]},
    {"id": "OD06", "corridor": "C6", "inbound": True, "origin": "N_ARADULUI_N", "destination": "N_COMPLEX",
     "label": "Calea Aradului → Complexul Studențesc", "base": 900, "paths": [
         ["N_ARADULUI_N", "N_IULIUS", "N_UNIRII", "N_BASTION", "N_CONTINENTAL", "N_BRATIANU", "N_MV_EROILOR", "N_COMPLEX"],
         ["N_ARADULUI_N", "N_IULIUS", "N_ROMANILOR", "N_TRAIAN", "N_3AUG_MID", "N_DECEBAL", "N_MV_E", "N_COMPLEX"],
     ]},
    {"id": "OD07", "corridor": "C1", "inbound": False, "origin": "N_CONTINENTAL", "destination": "N_SOARELUI",
     "label": "Cetate → Calea Martirilor", "paths": [
         ["N_CONTINENTAL", "N_BRATIANU", "N_MV_EROILOR", "N_CLUJ_S", "N_MARTIRILOR_S", "N_SOARELUI"],
         ["N_CONTINENTAL", "N_BRATIANU", "N_MV_EROILOR", "N_PARC_JUSTITIEI", "N_REBREANU", "N_MARTIRILOR_S", "N_SOARELUI"],
         ["N_CONTINENTAL", "N_DECEBAL", "N_MV_E", "N_COMPLEX", "N_CLUJ_S", "N_MARTIRILOR_S", "N_SOARELUI"],
     ]},
    {"id": "OD08", "corridor": "C2", "inbound": False, "origin": "N_TRAIAN", "destination": "N_DOJA",
     "label": "Fabric → Elisabetin (Piața Doina)", "paths": [
         ["N_TRAIAN", "N_3AUG_MID", "N_DECEBAL", "N_CONTINENTAL", "N_CATEDRALA", "N_MV_W", "N_DOJA"],
         ["N_TRAIAN", "N_ROMANILOR", "N_BASTION", "N_OPERA", "N_CATEDRALA", "N_MV_W", "N_DOJA"],
         ["N_TRAIAN", "N_3AUG_MID", "N_DECEBAL", "N_MV_E", "N_MV_EROILOR", "N_PARC_JUSTITIEI", "N_DOJA"],
     ]},
    {"id": "OD09", "corridor": "C3", "inbound": False, "origin": "N_PIATA_700", "destination": "N_DACIA",
     "label": "Cetate (Piața 700) → Dacia", "paths": [
         ["N_PIATA_700", "N_LAZAR_E", "N_LAZAR_W", "N_CIRC_N", "N_CIRC_DACIA_MID", "N_DACIA"],
         ["N_PIATA_700", "N_UNIRII", "N_IULIUS", "N_ARADULUI_N", "N_DACIA"],
         ["N_PIATA_700", "N_LAZAR_E", "N_LAZAR_W", "N_CIRC_W", "N_TORONTAL", "N_DACIA"],
     ]},
    {"id": "OD10", "corridor": "C4", "inbound": False, "origin": "N_CATEDRALA", "destination": "N_FRATELIA",
     "label": "Catedrală → Calea Șagului", "paths": [
         ["N_CATEDRALA", "N_CAROL_MID", "N_MARIA", "N_IOSEFIN", "N_SAGULUI", "N_FRATELIA"],
         ["N_CATEDRALA", "N_DRAGALINA", "N_GARA", "N_IOSEFIN", "N_SAGULUI", "N_FRATELIA"],
         ["N_CATEDRALA", "N_MV_W", "N_DOJA", "N_MOCIONI", "N_SAGULUI", "N_FRATELIA"],
     ]},
    {"id": "OD11", "corridor": "C5", "inbound": False, "origin": "N_OPERA", "destination": "N_LUGOJULUI",
     "label": "Operă → Calea Lugojului", "paths": [
         ["N_OPERA", "N_BASTION", "N_ROMANILOR", "N_TRAIAN", "N_LUGOJULUI"],
         ["N_OPERA", "N_CATEDRALA", "N_CONTINENTAL", "N_DECEBAL", "N_3AUG_MID", "N_TRAIAN", "N_LUGOJULUI"],
     ]},
    {"id": "OD12", "corridor": "C6", "inbound": False, "origin": "N_COMPLEX", "destination": "N_ARADULUI_N",
     "label": "Complexul Studențesc → Calea Aradului", "paths": [
         ["N_COMPLEX", "N_MV_E", "N_DECEBAL", "N_CONTINENTAL", "N_BASTION", "N_UNIRII", "N_IULIUS", "N_ARADULUI_N"],
         ["N_COMPLEX", "N_BUZIASULUI", "N_LUGOJULUI", "N_TRAIAN", "N_ROMANILOR", "N_IULIUS", "N_ARADULUI_N"],
     ]},
]


# Event attractor uplift on OD pairs ending at the attractor node (event_rush preset).
EVENT_ATTRACTOR_UPLIFT = 1.35
