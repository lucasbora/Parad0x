"""STPT transit seed (lines, fares). OWNER: Rareș. To be replaced by the live SMTT feed mapped to links.
"""
from __future__ import annotations

from typing import Any


# ---------------------------------------------------------------------------
# STPT transit lines (SMTT GTFS feed 4.31-4). type: 0 tram, 3 bus, 11 trolleybus
# ---------------------------------------------------------------------------

STPT_LINES: list[dict[str, Any]] = [
    {"routeId": "TB15", "shortName": "15", "type": 11, "color": "#0E7490", "headsign": "Piața Unirii",
     "nodes": ["N_MARTIRILOR_S", "N_CLUJ_S", "N_MV_EROILOR", "N_BRATIANU", "N_CONTINENTAL", "N_BASTION", "N_UNIRII"],
     "frequencyPerHour": 8, "firstDeparture": "05:10"},
    {"routeId": "TB16", "shortName": "16", "type": 11, "color": "#0369A1", "headsign": "Piața Victoriei",
     "nodes": ["N_SOARELUI", "N_MARTIRILOR_S", "N_CLUJ_S", "N_MV_EROILOR", "N_BRATIANU", "N_CONTINENTAL", "N_CATEDRALA", "N_OPERA"],
     "frequencyPerHour": 6, "firstDeparture": "05:20"},
    {"routeId": "BM11", "shortName": "M11", "type": 3, "color": "#7C3AED", "headsign": "Gara de Nord",
     "nodes": ["N_MARTIRILOR_S", "N_CLUJ_S", "N_MV_EROILOR", "N_BRATIANU", "N_CONTINENTAL", "N_CATEDRALA", "N_DRAGALINA", "N_GARA"],
     "frequencyPerHour": 4, "firstDeparture": "05:30"},
    {"routeId": "BE1", "shortName": "E1", "type": 3, "color": "#DC2626", "headsign": "Calea Lugojului",
     "nodes": ["N_MARIA", "N_CAROL_MID", "N_CATEDRALA", "N_CONTINENTAL", "N_DECEBAL", "N_3AUG_MID", "N_TRAIAN", "N_LUGOJULUI"],
     "frequencyPerHour": 6, "firstDeparture": "05:05"},
    {"routeId": "BE2", "shortName": "E2", "type": 3, "color": "#EA580C", "headsign": "Calea Lipovei",
     "nodes": ["N_GARA", "N_IOSEFIN", "N_MARIA", "N_CAROL_MID", "N_CATEDRALA", "N_CONTINENTAL", "N_BASTION", "N_ROMANILOR", "N_LIPOVEI"],
     "frequencyPerHour": 5, "firstDeparture": "05:15"},
    {"routeId": "B33", "shortName": "33", "type": 3, "color": "#CA8A04", "headsign": "Complexul Studențesc",
     "nodes": ["N_SAGULUI", "N_IOSEFIN", "N_MARIA", "N_CAROL_MID", "N_CATEDRALA", "N_CONTINENTAL", "N_DECEBAL", "N_MV_E", "N_COMPLEX"],
     "frequencyPerHour": 6, "firstDeparture": "05:00"},
    {"routeId": "TR1", "shortName": "1", "type": 0, "color": "#B91C1C", "headsign": "Piața Traian",
     "nodes": ["N_GARA", "N_DRAGALINA", "N_CATEDRALA", "N_CONTINENTAL", "N_DECEBAL", "N_3AUG_MID", "N_TRAIAN"],
     "frequencyPerHour": 8, "firstDeparture": "04:50"},
    {"routeId": "TR2", "shortName": "2", "type": 0, "color": "#BE185D", "headsign": "Piața Unirii",
     "nodes": ["N_16DEC_W", "N_IOSEFIN", "N_MARIA", "N_CAROL_MID", "N_CATEDRALA", "N_CONTINENTAL", "N_BASTION", "N_UNIRII"],
     "frequencyPerHour": 7, "firstDeparture": "04:55"},
    {"routeId": "TB14", "shortName": "14", "type": 11, "color": "#0891B2", "headsign": "Piața Unirii",
     "nodes": ["N_DACIA", "N_CIRC_DACIA_MID", "N_CIRC_N", "N_LAZAR_W", "N_LAZAR_E", "N_PIATA_700", "N_UNIRII"],
     "frequencyPerHour": 7, "firstDeparture": "05:10"},
    {"routeId": "B40", "shortName": "40", "type": 3, "color": "#65A30D", "headsign": "Piața Victoriei",
     "nodes": ["N_TORONTAL", "N_CIRC_W", "N_LAZAR_W", "N_LAZAR_E", "N_PIATA_700", "N_OPERA"],
     "frequencyPerHour": 4, "firstDeparture": "05:25"},
    {"routeId": "TR8", "shortName": "8", "type": 0, "color": "#9F1239", "headsign": "Calea Lipovei",
     "nodes": ["N_ARADULUI_N", "N_IULIUS", "N_UNIRII", "N_BASTION", "N_ROMANILOR", "N_LIPOVEI"],
     "frequencyPerHour": 6, "firstDeparture": "05:00"},
]


VEHICLE_CAPACITY = {0: 120, 3: 70, 11: 80}  # average peak load (passengers) by GTFS type


STPT_FARES = [
    {"id": "bilet-60", "name_ro": "Bilet 60 de minute", "name_en": "60-minute ticket", "priceRon": 5.0},
    {"id": "abonament-zi", "name_ro": "Abonament 1 zi", "name_en": "Day pass", "priceRon": 18.0},
]


def transit_network_payload() -> dict[str, Any]:
    """Shape of /api/mobile/transit/network (seeded)."""
    return {
        "feedVersion": "4.31-4",
        "validFrom": "2026-11-01",
        "validTo": "2026-12-31",
        "routes": [
            {"routeId": l["routeId"], "shortName": l["shortName"], "type": l["type"], "color": l["color"]}
            for l in STPT_LINES
        ],
    }
