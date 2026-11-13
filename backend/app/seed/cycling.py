"""Cycling seed: cycleways, bike corridors and i'velo stations.

OWNER: Laura. ILLUSTRATIVE — to be replaced by real OSM cycleways and i'velo stations.
"""
from __future__ import annotations

import random
from typing import Any

from app.seed.network import NODES


# ---------------------------------------------------------------------------
# Cycling: OSM-style cycleways, bike corridors (A* OD pairs) and i'velo stations
# ---------------------------------------------------------------------------

OSM_CYCLEWAYS: list[dict[str, Any]] = [
    {"id": "cw_bega_n", "name": "Pista Velo Bega (mal nord)", "coordinates": [
        [21.2010, 45.7518], [21.2080, 45.7522], [21.2140, 45.7524], [21.2210, 45.7514],
        [21.2260, 45.7500], [21.2320, 45.7508], [21.2390, 45.7526], [21.2460, 45.7536]]},
    {"id": "cw_bega_s", "name": "Pista Velo Bega (mal sud)", "coordinates": [
        [21.2080, 45.7505], [21.2170, 45.7490], [21.2275, 45.7484], [21.2330, 45.7474], [21.2395, 45.7500]]},
    {"id": "cw_mercy", "name": "Str. Mercy", "coordinates": [[21.2218, 45.7592], [21.2290, 45.7580]]},
    {"id": "cw_titulescu", "name": "Splaiul Nicolae Titulescu", "coordinates": [
        [21.2138, 45.7528], [21.2190, 45.7520], [21.2243, 45.7508]]},
    {"id": "cw_decebal", "name": "Podul Decebal", "coordinates": [[21.2395, 45.7505], [21.2405, 45.7548]]},
    {"id": "cw_aradului", "name": "Calea Aradului (pistă pe trotuar)", "coordinates": [
        [21.2290, 45.7580], [21.2286, 45.7620], [21.2282, 45.7665]]},
    {"id": "cw_complex", "name": "Aleea Studenților", "coordinates": [
        [21.2398, 45.7460], [21.2420, 45.7440], [21.2440, 45.7425]]},
    {"id": "cw_lipovei", "name": "Calea Lipovei (segment)", "coordinates": [[21.2375, 45.7620], [21.2415, 45.7700]]},
    {"id": "cw_martirilor_s", "name": "Calea Martirilor (Sud, segment)", "coordinates": [
        [21.2402, 45.7328], [21.2430, 45.7260]]},
    {"id": "cw_dacia", "name": "Str. Dacia (segment)", "coordinates": [[21.2210, 45.7720], [21.2240, 45.7735]]},
    {"id": "cw_parc_rozelor", "name": "Parcul Rozelor", "coordinates": [
        [21.2300, 45.7495], [21.2340, 45.7500], [21.2370, 45.7512]]},
    {"id": "cw_justitiei", "name": "Parcul Justiției (alee)", "coordinates": [
        [21.2290, 45.7448], [21.2302, 45.7442], [21.2318, 45.7436]]},
]


BIKE_CORRIDORS: list[dict[str, Any]] = [
    {"id": "BIKE_CLUJ_JUSTITIEI", "name": "Complexul Studențesc ↔ Parcul Justiției",
     "origin": "N_CLUJ_S", "destination": "N_PARC_JUSTITIEI",
     "originName": "Complexul Studențesc (Str. Cluj)", "destinationName": "Parcul Justiției"},
    {"id": "BIKE_CATEDRALA_TRAIAN", "name": "Catedrala ↔ Piața Traian",
     "origin": "N_CATEDRALA", "destination": "N_TRAIAN",
     "originName": "Catedrala Mitropolitană", "destinationName": "Piața Traian"},
    {"id": "BIKE_DACIA_UNIRII", "name": "Dacia ↔ Piața Unirii",
     "origin": "N_DACIA", "destination": "N_UNIRII",
     "originName": "Cartier Dacia", "destinationName": "Piața Unirii"},
    {"id": "BIKE_GARA_CATEDRALA", "name": "Gara de Nord ↔ Catedrala",
     "origin": "N_GARA", "destination": "N_CATEDRALA",
     "originName": "Gara de Nord", "destinationName": "Catedrala Mitropolitană"},
    {"id": "BIKE_SAGULUI_UNIRII", "name": "Calea Șagului ↔ Piața Unirii",
     "origin": "N_SAGULUI", "destination": "N_UNIRII",
     "originName": "Calea Șagului", "destinationName": "Piața Unirii"},
    {"id": "BIKE_COMPLEX_UNIRII", "name": "Complexul Studențesc ↔ Piața Unirii",
     "origin": "N_COMPLEX", "destination": "N_UNIRII",
     "originName": "Complexul Studențesc", "destinationName": "Piața Unirii"},
]


_IVELO_NAMED: list[tuple[str, float, float]] = [
    ("Piața Unirii", 21.2296, 45.7578), ("Piața Victoriei", 21.2255, 45.7530),
    ("Catedrala Mitropolitană", 21.2236, 45.7514), ("Bastionul Theresia", 21.2342, 45.7562),
    ("Piața 700", 21.2212, 45.7596), ("Piața Maria", 21.2176, 45.7502),
    ("Piața Bălcescu", 21.2094, 45.7480), ("Gara de Nord", 21.2062, 45.7512),
    ("Parcul Rozelor", 21.2330, 45.7502), ("Parcul Justiției", 21.2298, 45.7446),
    ("Complexul Studențesc — Cămin C12", 21.2405, 45.7466), ("Str. Cluj — Politehnica", 21.2352, 45.7440),
    ("Calea Martirilor — Str. Cluj", 21.2372, 45.7415), ("UVT — Bd. Vasile Pârvan", 21.2290, 45.7472),
    ("Piața Traian", 21.2468, 45.7586), ("Podul Decebal", 21.2410, 45.7540),
    ("Piața Romanilor", 21.2380, 45.7626), ("Iulius Town", 21.2290, 45.7668),
    ("Dacia — Piața Dacia", 21.2215, 45.7724), ("Circumvalațiunii — Gh. Lazăr", 21.2124, 45.7638),
    ("Parcul Botanic", 21.2240, 45.7615), ("Piața Doina", 21.2216, 45.7466),
    ("Calea Șagului — Spitalul Județean", 21.2112, 45.7390), ("Calea Buziașului", 21.2520, 45.7420),
]


def ivelo_stations() -> list[dict[str, Any]]:
    """49 i'velo bike-share stations (24 named + 25 deterministic neighbourhood docks)."""
    stations = [
        {"id": f"IVELO_{i + 1:02d}", "name": f"i'velo — {name}", "coordinates": [lng, lat],
         "capacity": 12 + (i * 5) % 9, "bikesAvailable": 3 + (i * 7) % 10}
        for i, (name, lng, lat) in enumerate(_IVELO_NAMED)
    ]
    rng = random.Random(1042)
    node_ids = sorted(NODES)
    for j in range(49 - len(stations)):
        nid = node_ids[(j * 7) % len(node_ids)]
        name, lng, lat, cartier, _ = NODES[nid]
        stations.append({
            "id": f"IVELO_{len(stations) + 1:02d}",
            "name": f"i'velo — {cartier} #{j + 1}",
            "coordinates": [round(lng + rng.uniform(-0.0025, 0.0025), 6), round(lat + rng.uniform(-0.0018, 0.0018), 6)],
            "capacity": 10 + j % 6,
            "bikesAvailable": (j * 3) % 9,
        })
    return stations
