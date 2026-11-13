"""Deterministic, self-contained seed dataset for central Timișoara.

This is the offline-first fallback required by the City Hall Data & Services
Guide: if any PMT / SMTT / Overpass endpoint is down, slow (>4 s) or returns
non-200, the simulator keeps working from this module.

Coordinates are WGS84 ``[lng, lat]`` (GeoJSON order). Node positions are
approximate street-intersection locations in central Timișoara; link geometry is
straight-line between intersections, so it is schematic rather than surveyed.
Everything here is deterministic: no randomness without a fixed seed.
"""
from __future__ import annotations

import math
import random
import unicodedata
from typing import Any

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


# ---------------------------------------------------------------------------
# Nodes (intersections / centroids)
# id: (name, lng, lat, cartier, signalized)
# ---------------------------------------------------------------------------

NODES: dict[str, tuple[str, float, float, str, bool]] = {
    # Cetate
    "N_UNIRII": ("Piața Unirii", 21.2290, 45.7580, "Cetate", True),
    "N_OPERA": ("Piața Victoriei (Operă)", 21.2262, 45.7540, "Cetate", True),
    "N_CATEDRALA": ("Catedrala Mitropolitană", 21.2243, 45.7508, "Cetate", True),
    "N_CONTINENTAL": ("Bd. Regele Ferdinand I / Hotel Continental", 21.2318, 45.7530, "Cetate", True),
    "N_BASTION": ("Bastionul Theresia", 21.2338, 45.7568, "Cetate", True),
    "N_PIATA_700": ("Piața 700", 21.2218, 45.7592, "Cetate", True),
    # Iosefin
    "N_MARIA": ("Piața Maria", 21.2172, 45.7497, "Iosefin", True),
    "N_IOSEFIN": ("Piața Nicolae Bălcescu (Iosefin)", 21.2100, 45.7476, "Iosefin", True),
    "N_GARA": ("Gara de Nord", 21.2068, 45.7508, "Iosefin", True),
    "N_DRAGALINA": ("Podul Iosefin / Bd. Gen. Ion Dragalina", 21.2138, 45.7528, "Iosefin", True),
    "N_MOCIONI": ("Piața Alexandru Mocioni", 21.2148, 45.7448, "Iosefin", True),
    "N_16DEC_W": ("Bd. 16 Decembrie 1989 (Vest)", 21.2030, 45.7462, "Iosefin", False),
    "N_SAGULUI": ("Calea Șagului", 21.2118, 45.7385, "Calea Șagului", True),
    # Elisabetin / south bank
    "N_DOJA": ("Str. Gheorghe Doja / Piața Doina", 21.2212, 45.7462, "Elisabetin", True),
    "N_MV_W": ("Bd. Mihai Viteazul / Podul Mihai Viteazul", 21.2275, 45.7488, "Elisabetin", True),
    "N_MV_EROILOR": ("Bd. Mihai Viteazul / Bd. Eroilor de la Tisa", 21.2330, 45.7478, "Complexul Studențesc", True),
    "N_MV_E": ("Bd. Mihai Viteazul / Podul Decebal", 21.2395, 45.7505, "Complexul Studențesc", True),
    "N_PARC_JUSTITIEI": ("Parcul Justiției", 21.2302, 45.7442, "Elisabetin", True),
    "N_REBREANU": ("Bd. Liviu Rebreanu / Str. Ion Ionescu de la Brad", 21.2268, 45.7392, "Elisabetin", True),
    # Complexul Studențesc / Martirilor
    "N_COMPLEX": ("Complexul Studențesc", 21.2398, 45.7460, "Complexul Studențesc", True),
    "N_CLUJ_S": ("Calea Martirilor / Str. Cluj", 21.2368, 45.7410, "Complexul Studențesc", True),
    "N_MARTIRILOR_S": ("Calea Martirilor (Sud)", 21.2402, 45.7328, "Calea Martirilor", True),
    "N_BUZIASULUI": ("Calea Buziașului", 21.2525, 45.7415, "Calea Buziașului", True),
    # Fabric / east
    "N_DECEBAL": ("Podul Decebal / Bd. 3 August 1919", 21.2405, 45.7548, "Fabric", True),
    "N_TRAIAN": ("Piața Traian", 21.2462, 45.7582, "Fabric", True),
    "N_LUGOJULUI": ("Calea Lugojului / Str. Ștefan cel Mare", 21.2585, 45.7562, "Calea Lugojului", True),
    "N_ROMANILOR": ("Piața Romanilor", 21.2375, 45.7620, "Badea Cârțan", True),
    "N_LIPOVEI": ("Calea Lipovei", 21.2415, 45.7700, "Calea Lipovei", True),
    # North
    "N_IULIUS": ("Calea Aradului / Bd. Cetății", 21.2282, 45.7665, "Calea Aradului", True),
    "N_ARADULUI_N": ("Calea Aradului (Nord)", 21.2290, 45.7745, "Calea Aradului", True),
    "N_DACIA": ("Cartier Dacia", 21.2210, 45.7720, "Dacia", True),
    "N_CIRC_N": ("Calea Circumvalațiunii / Bd. Cetății", 21.2172, 45.7680, "Circumvalațiunii", True),
    "N_LAZAR_W": ("Calea Circumvalațiunii / Str. Gheorghe Lazăr", 21.2118, 45.7635, "Circumvalațiunii", True),
    "N_LAZAR_E": ("Str. Gheorghe Lazăr / Str. Ana Ipătescu", 21.2190, 45.7615, "Circumvalațiunii", True),
    "N_CIRC_W": ("Calea Circumvalațiunii (Sud-Vest)", 21.2068, 45.7588, "Circumvalațiunii", True),
    "N_TORONTAL": ("Calea Torontalului", 21.2000, 45.7660, "Calea Torontalului", True),
    "N_MEHALA": ("Mehala (Str. Gării / Bd. Cetății Vest)", 21.1975, 45.7560, "Mehala", False),
    "N_SOARELUI": ("Calea Martirilor / Str. Lunei (Soarelui)", 21.2430, 45.7260, "Soarelui", False),
    "N_GIROCULUI": ("Calea Girocului", 21.2250, 45.7300, "Calea Girocului", True),
    "N_KUNTZ": ("Str. Ștefan cel Mare / Kuntz", 21.2640, 45.7625, "Kuntz", False),
    "N_TIPOGRAFILOR": ("Str. Tipografilor / Calea Lipovei", 21.2445, 45.7755, "Tipografilor", False),
    "N_FRATELIA": ("Fratelia (Calea Șagului Sud)", 21.2040, 45.7330, "Fratelia", False),
    # Interior signalised intersections on the shared Braess legs
    "N_BRATIANU": ("Podul Eroilor / Str. Ion C. Brătianu", 21.2326, 45.7505, "Cetate", True),
    "N_CAROL_MID": ("Bd. Regele Carol I / Str. Mărășești", 21.2208, 45.7503, "Iosefin", True),
    "N_3AUG_MID": ("Bd. 3 August 1919 / Str. Romulus", 21.2432, 45.7566, "Fabric", True),
    "N_CIRC_DACIA_MID": ("Calea Circumvalațiunii / Str. Ovidiu Balea", 21.2190, 45.7700, "Dacia", True),
}


# ---------------------------------------------------------------------------
# Street segments. Each produces two directed road links (_01 forward, _02 back)
# unless ``oneway`` is set.
# (tag, from, to, street name, codGis, lanes, speed_kmh, options)
# lanes is the *directional* cross-section (curb parking included).
# ---------------------------------------------------------------------------

Seg = tuple[str, str, str, str, str, list[str], float, dict[str, Any]]

SEGMENTS: list[Seg] = [
    # --- Featured Braess hotspots -------------------------------------------------
    ("CLUJ", "N_CLUJ_S", "N_MV_EROILOR", "Strada Cluj", "1042",
     ["car", "car", "parking_blue"], 40, {"hotspot": "HOTSPOT_CLUJ_EROILOR", "length_m": 800}),
    ("FERDINAND", "N_CATEDRALA", "N_CONTINENTAL", "Bd. Regele Ferdinand I", "0218",
     ["car", "car"], 40, {"hotspot": "HOTSPOT_FERDINAND_CATEDRALA", "length_m": 560}),
    ("CIRCUMVALATIUNII", "N_CIRC_N", "N_LAZAR_W", "Calea Circumvalațiunii", "0389",
     ["car", "car", "car"], 50, {"hotspot": "HOTSPOT_CIRCUMVALATIUNII", "length_m": 600}),
    ("16DEC", "N_IOSEFIN", "N_MARIA", "Bd. 16 Decembrie 1989", "0815",
     ["car", "car", "parking_red"], 40, {"hotspot": "HOTSPOT_SESIZARI_IOSEFIN", "length_m": 450}),

    # --- Cetate ring ----------------------------------------------------------------
    ("REVOLUTIEI", "N_UNIRII", "N_BASTION", "Bd. Revoluției din 1989", "0102",
     ["car", "car", "parking_green"], 40, {}),
    ("MERCY", "N_PIATA_700", "N_UNIRII", "Str. Mercy", "0131",
     ["car", "parking_green"], 30, {"cycleway": True}),
    ("LOGA", "N_PIATA_700", "N_OPERA", "Bd. C. D. Loga", "0117",
     ["car", "car"], 40, {}),
    ("LOGA_S", "N_OPERA", "N_CATEDRALA", "Bd. C. D. Loga (Sud)", "0118",
     ["car", "car"], 40, {}),
    ("REPUBLICII", "N_OPERA", "N_BASTION", "Bd. Republicii", "0145",
     ["car", "car", "parking_green"], 40, {}),
    ("HECTOR", "N_CONTINENTAL", "N_BASTION", "Str. Hector", "0152",
     ["car", "parking_green"], 30, {}),
    ("SPLAI_TV", "N_CONTINENTAL", "N_DECEBAL", "Splaiul Tudor Vladimirescu", "0233",
     ["car", "car"], 45, {"length_m": 720}),
    # --- Fabric -------------------------------------------------------------------
    ("3AUGUST", "N_DECEBAL", "N_3AUG_MID", "Bd. 3 August 1919", "0611",
     ["car", "car", "parking_yellow"], 40, {}),
    ("3AUGUST_E", "N_3AUG_MID", "N_TRAIAN", "Bd. 3 August 1919 (Est)", "0612",
     ["car", "car", "parking_yellow"], 40, {}),
    ("STEFAN", "N_TRAIAN", "N_LUGOJULUI", "Str. Ștefan cel Mare", "0640",
     ["car", "car"], 50, {}),
    ("DACILOR", "N_ROMANILOR", "N_TRAIAN", "Str. Dacilor", "0622",
     ["car", "parking_yellow"], 40, {}),
    ("TAKE", "N_BASTION", "N_ROMANILOR", "Bd. Take Ionescu", "0510",
     ["car", "car"], 45, {}),
    ("LIPOVEI", "N_ROMANILOR", "N_LIPOVEI", "Calea Lipovei", "0705",
     ["car", "car"], 50, {}),
    ("KUNTZ", "N_LUGOJULUI", "N_KUNTZ", "Str. Ștefan cel Mare (Est)", "0641",
     ["car", "car"], 50, {}),
    ("TIPOGRAFILOR", "N_LIPOVEI", "N_TIPOGRAFILOR", "Str. Tipografilor", "0712",
     ["car"], 40, {}),
    # --- North / Calea Aradului / Circumvalațiunii -------------------------------
    ("ARADULUI_S", "N_UNIRII", "N_IULIUS", "Calea Aradului (Sud)", "0301",
     ["car", "car"], 45, {}),
    ("ARADULUI", "N_IULIUS", "N_ARADULUI_N", "Calea Aradului", "0302",
     ["car", "car", "car"], 50, {}),
    ("CETATII_E", "N_IULIUS", "N_ROMANILOR", "Bd. Cetății (Est)", "0320",
     ["car", "car"], 50, {}),
    ("CETATII", "N_CIRC_N", "N_IULIUS", "Bd. Cetății", "0321",
     ["car", "car"], 50, {"length_m": 900}),
    ("CIRC_DACIA", "N_DACIA", "N_CIRC_DACIA_MID", "Calea Circumvalațiunii (Dacia)", "0388",
     ["car", "car"], 50, {}),
    ("CIRC_BALEA", "N_CIRC_DACIA_MID", "N_CIRC_N", "Calea Circumvalațiunii (Balea)", "0387",
     ["car", "car"], 50, {}),
    ("DIVIZIA9", "N_DACIA", "N_ARADULUI_N", "Str. Divizia 9 Cavalerie", "0395",
     ["car", "parking_blue"], 40, {}),
    ("LAZAR", "N_LAZAR_W", "N_LAZAR_E", "Str. Gheorghe Lazăr", "0402",
     ["car", "car"], 40, {}),
    ("LAZAR_E", "N_LAZAR_E", "N_PIATA_700", "Str. Gheorghe Lazăr (Est)", "0403",
     ["car", "car"], 40, {}),
    ("TORONTAL", "N_DACIA", "N_TORONTAL", "Calea Torontalului", "0420",
     ["car", "car"], 50, {"length_m": 1700}),
    ("TORONTAL_S", "N_TORONTAL", "N_CIRC_W", "Calea Torontalului (Sud)", "0421",
     ["car", "car"], 50, {}),
    ("CIRC_SW", "N_CIRC_W", "N_LAZAR_W", "Calea Circumvalațiunii (Sud)", "0390",
     ["car", "car"], 50, {}),
    ("MEHALA", "N_MEHALA", "N_CIRC_W", "Str. Gării (Mehala)", "0430",
     ["car", "car"], 45, {}),
    ("MEHALA_GARA", "N_MEHALA", "N_GARA", "Str. Gării", "0431",
     ["car", "car"], 45, {}),
    ("DRAGALINA_N", "N_CIRC_W", "N_DRAGALINA", "Bd. Gen. Ion Dragalina (Nord)", "0850",
     ["car", "car"], 45, {}),
    # --- Iosefin ------------------------------------------------------------------
    ("DRAGALINA", "N_DRAGALINA", "N_GARA", "Bd. Gen. Ion Dragalina", "0851",
     ["car", "car"], 40, {}),
    ("TITULESCU", "N_DRAGALINA", "N_CATEDRALA", "Splaiul Nicolae Titulescu", "0860",
     ["car", "car"], 45, {"cycleway": True, "length_m": 1150}),
    ("VACARESCU", "N_GARA", "N_IOSEFIN", "Str. Iancu Văcărescu", "0820",
     ["car", "parking_red"], 40, {}),
    ("16DEC_W", "N_16DEC_W", "N_IOSEFIN", "Bd. 16 Decembrie 1989 (Vest)", "0814",
     ["car", "car"], 50, {}),
    ("GARII_W", "N_GARA", "N_16DEC_W", "Str. Gării (Vest)", "0821",
     ["car"], 40, {}),
    ("SAGULUI", "N_SAGULUI", "N_IOSEFIN", "Calea Șagului", "0870",
     ["car", "car"], 50, {}),
    ("POP", "N_SAGULUI", "N_MOCIONI", "Str. Ion Pop de Iasomie", "0872",
     ["car", "car"], 40, {"length_m": 1500}),
    ("MOCIONI", "N_MOCIONI", "N_MARIA", "Str. Andrei Mocioni", "0873",
     ["car", "car"], 40, {}),
    ("CAROL", "N_MARIA", "N_CAROL_MID", "Bd. Regele Carol I", "0201",
     ["car", "car"], 45, {}),
    ("CAROL_E", "N_CAROL_MID", "N_CATEDRALA", "Bd. Regele Carol I (Est)", "0202",
     ["car", "car"], 45, {}),
    ("FRATELIA", "N_FRATELIA", "N_SAGULUI", "Calea Șagului (Sud)", "0871",
     ["car", "car"], 50, {}),
    # --- South bank (Elisabetin / Complex) ---------------------------------------
    ("SPLAI_COL", "N_MARIA", "N_MV_W", "Splaiul Coloniei", "0705B",
     ["car", "car"], 45, {"cycleway": True, "length_m": 1500}),
    ("PODUL_MV", "N_MV_W", "N_CATEDRALA", "Podul Mihai Viteazul", "0220",
     ["car", "car"], 40, {}),
    ("MV", "N_MV_W", "N_MV_EROILOR", "Bd. Mihai Viteazul", "1001",
     ["car", "car"], 30, {"cycleway": True, "length_m": 820}),
    ("MV_E", "N_MV_EROILOR", "N_MV_E", "Bd. Mihai Viteazul (Est)", "1002",
     ["car", "car"], 45, {"cycleway": True}),
    ("PODUL_EROILOR", "N_MV_EROILOR", "N_BRATIANU", "Podul Eroilor", "1003",
     ["car", "car"], 40, {}),
    ("BRATIANU", "N_BRATIANU", "N_CONTINENTAL", "Str. Ion C. Brătianu", "0230",
     ["car", "car"], 40, {}),
    ("PODUL_DECEBAL", "N_MV_E", "N_DECEBAL", "Podul Decebal", "1004",
     ["car", "car"], 40, {"cycleway": True}),
    ("EROILOR", "N_MV_EROILOR", "N_COMPLEX", "Bd. Eroilor de la Tisa", "1040",
     ["car", "car"], 45, {}),
    ("PARIS", "N_COMPLEX", "N_MV_E", "Str. Paris", "1041",
     ["car", "car"], 40, {}),
    ("MARTIRILOR_N", "N_CLUJ_S", "N_COMPLEX", "Calea Martirilor (Nord)", "1050",
     ["car", "car"], 45, {"length_m": 650}),
    ("MARTIRILOR", "N_MARTIRILOR_S", "N_CLUJ_S", "Calea Martirilor", "1051",
     ["car", "car"], 50, {}),
    ("REBREANU", "N_MARTIRILOR_S", "N_REBREANU", "Bd. Liviu Rebreanu", "1060",
     ["car", "car"], 50, {"length_m": 1350}),
    ("BRAD", "N_REBREANU", "N_PARC_JUSTITIEI", "Str. Ion Ionescu de la Brad", "1061",
     ["car", "car"], 45, {"length_m": 950}),
    ("JUSTITIEI", "N_PARC_JUSTITIEI", "N_MV_EROILOR", "Str. Gheorghe Adam", "1062",
     ["car", "car"], 45, {"length_m": 600}),
    ("ODOBESCU", "N_PARC_JUSTITIEI", "N_DOJA", "Str. Alexandru Odobescu", "1063",
     ["car", "parking_yellow"], 40, {}),
    ("DOJA", "N_DOJA", "N_MV_W", "Str. Gheorghe Doja", "1070",
     ["car", "car"], 40, {}),
    ("DOJA_W", "N_DOJA", "N_MOCIONI", "Str. Ștefan Octavian Iosif", "1071",
     ["car", "parking_yellow"], 40, {}),
    ("REBREANU_W", "N_REBREANU", "N_SAGULUI", "Bd. Liviu Rebreanu (Vest)", "1064",
     ["car", "car"], 50, {}),
    ("BUZIAS_N", "N_COMPLEX", "N_BUZIASULUI", "Calea Buziașului (Nord)", "1080",
     ["car", "car"], 50, {}),
    ("BUZIAS", "N_BUZIASULUI", "N_LUGOJULUI", "Calea Buziașului", "1081",
     ["car", "car"], 50, {}),
    ("SOARELUI", "N_SOARELUI", "N_MARTIRILOR_S", "Calea Martirilor (Soarelui)", "1052",
     ["car", "car"], 50, {}),
    ("GIROCULUI", "N_GIROCULUI", "N_REBREANU", "Calea Girocului", "1090",
     ["car", "car"], 50, {}),
]


# ---------------------------------------------------------------------------
# Phantom intersection queue links (Burov et al.)
# (id, node, in_link, out_link, cycle_s, red_s, n_per_lane, alpha_s_per_vehh, control)
# n = vehicles discharged per green per approaching car lane. s = 3600 n m_car / D.
# ---------------------------------------------------------------------------

QUEUE_MOVEMENTS: list[tuple[str, str, str, str, float, float, float, float, str]] = [
    # Hotspot 1 — Str. Cluj cut-through between Calea Martirilor and Podul Eroilor
    ("Q_MARTS_SHARED", "N_MARTIRILOR_S", "LINK_SOARELUI_01", "LINK_MARTIRILOR_01", 90, 45, 11.5, 0.18, "signal"),
    ("Q_MV_CLUJ_PODUL", "N_MV_EROILOR", "LINK_CLUJ_01", "LINK_PODUL_EROILOR_01", 90, 45, 11.5, 0.18, "signal"),
    ("Q_MV_JUST_PODUL", "N_MV_EROILOR", "LINK_JUSTITIEI_01", "LINK_PODUL_EROILOR_01", 90, 45, 11.5, 0.18, "signal"),
    ("Q_MV_EROILOR_PODUL", "N_MV_EROILOR", "LINK_EROILOR_02", "LINK_PODUL_EROILOR_01", 90, 55, 11.5, 0.18, "signal"),
    ("Q_MV_MVW_PODUL", "N_MV_EROILOR", "LINK_MV_01", "LINK_PODUL_EROILOR_01", 90, 55, 11.5, 0.18, "signal"),
    ("Q_BRATIANU_SHARED", "N_BRATIANU", "LINK_PODUL_EROILOR_01", "LINK_BRATIANU_01", 90, 45, 11.5, 0.18, "signal"),
    ("Q_PODUL_CLUJ_OUT", "N_MV_EROILOR", "LINK_PODUL_EROILOR_02", "LINK_CLUJ_02", 90, 45, 11.5, 0.18, "signal"),
    # Hotspot 2 — Bd. Regele Ferdinand I cut-through between Bd. Carol I and the Splai
    ("Q_CAROL_SHARED", "N_CAROL_MID", "LINK_CAROL_01", "LINK_CAROL_E_01", 90, 45, 11.5, 0.17, "signal"),
    ("Q_PODMV_SHARED", "N_MV_W", "LINK_DOJA_01", "LINK_PODUL_MV_01", 90, 45, 11.5, 0.17, "signal"),
    ("Q_CAT_POD_FERD", "N_CATEDRALA", "LINK_PODUL_MV_01", "LINK_FERDINAND_01", 90, 45, 11.5, 0.16, "signal"),
    ("Q_CAT_POD_LOGA", "N_CATEDRALA", "LINK_PODUL_MV_01", "LINK_LOGA_S_02", 90, 45, 11.5, 0.16, "signal"),
    ("Q_CAT_CAROL_LOGA", "N_CATEDRALA", "LINK_CAROL_E_01", "LINK_LOGA_S_02", 90, 45, 11.5, 0.16, "signal"),
    ("Q_CAT_TIT_LOGA", "N_CATEDRALA", "LINK_TITULESCU_01", "LINK_LOGA_S_02", 90, 50, 11.5, 0.16, "signal"),
    ("Q_CONT_FERD_SPLAI", "N_CONTINENTAL", "LINK_FERDINAND_01", "LINK_SPLAI_TV_01", 90, 45, 11.5, 0.16, "signal"),
    ("Q_CONT_BRAT_SPLAI", "N_CONTINENTAL", "LINK_BRATIANU_01", "LINK_SPLAI_TV_01", 90, 45, 11.5, 0.16, "signal"),
    ("Q_CONT_SPLAI_FERD", "N_CONTINENTAL", "LINK_SPLAI_TV_02", "LINK_FERDINAND_02", 90, 45, 11.5, 0.16, "signal"),
    ("Q_3AUG_SHARED", "N_3AUG_MID", "LINK_3AUGUST_01", "LINK_3AUGUST_E_01", 90, 45, 11.5, 0.17, "signal"),
    ("Q_DECEBAL_SPLAI_3AUG", "N_DECEBAL", "LINK_SPLAI_TV_01", "LINK_3AUGUST_01", 90, 45, 11.5, 0.15, "signal"),
    ("Q_DECEBAL_POD_3AUG", "N_DECEBAL", "LINK_PODUL_DECEBAL_01", "LINK_3AUGUST_01", 90, 45, 11.5, 0.15, "signal"),
    # Hotspot 3 — Calea Circumvalațiunii cut-through into the Gh. Lazăr merge
    ("Q_BALEA_SHARED", "N_CIRC_DACIA_MID", "LINK_CIRC_DACIA_01", "LINK_CIRC_BALEA_01", 80, 40, 11.0, 0.17, "signal"),
    ("Q_LAZAR_CIRC_MERGE", "N_LAZAR_W", "LINK_CIRCUMVALATIUNII_01", "LINK_LAZAR_01", 80, 40, 11.0, 0.17, "signal"),
    ("Q_LAZAR_SW_MERGE", "N_LAZAR_W", "LINK_CIRC_SW_01", "LINK_LAZAR_01", 80, 40, 11.0, 0.17, "signal"),
    ("Q_LAZARE_SHARED", "N_LAZAR_E", "LINK_LAZAR_01", "LINK_LAZAR_E_01", 80, 40, 11.0, 0.17, "signal"),
    ("Q_LAZAR_OUT_CIRC", "N_LAZAR_W", "LINK_LAZAR_02", "LINK_CIRCUMVALATIUNII_02", 80, 40, 11.0, 0.17, "signal"),
    ("Q_IULIUS_CETATII_ARAD", "N_IULIUS", "LINK_CETATII_01", "LINK_ARADULUI_S_02", 90, 45, 11.5, 0.15, "signal"),
    # Hotspot 4 — Bd. 16 Decembrie 1989 cut-through between Calea Șagului and Piața Maria
    ("Q_SAGULUI_SHARED", "N_SAGULUI", "LINK_FRATELIA_01", "LINK_SAGULUI_01", 90, 45, 11.5, 0.17, "signal"),
    ("Q_IOSEFIN_SAG_16DEC", "N_IOSEFIN", "LINK_SAGULUI_01", "LINK_16DEC_01", 90, 45, 11.5, 0.16, "signal"),
    ("Q_MARIA_16DEC_CAROL", "N_MARIA", "LINK_16DEC_01", "LINK_CAROL_01", 90, 45, 11.5, 0.17, "signal"),
    ("Q_MARIA_MOCIONI_CAROL", "N_MARIA", "LINK_MOCIONI_01", "LINK_CAROL_01", 90, 45, 11.5, 0.17, "signal"),
    ("Q_MARIA_CAROL_16DEC", "N_MARIA", "LINK_CAROL_02", "LINK_16DEC_02", 90, 45, 11.5, 0.17, "signal"),
    # Background signalised movements
    ("Q_BASTION_REP_TAKE", "N_BASTION", "LINK_REPUBLICII_01", "LINK_TAKE_01", 90, 45, 11.5, 0.15, "signal"),
    ("Q_OPERA_LOGA_REP", "N_OPERA", "LINK_LOGA_S_02", "LINK_REPUBLICII_01", 90, 45, 11.5, 0.15, "signal"),
    ("Q_ROM_TAKE_DACILOR", "N_ROMANILOR", "LINK_TAKE_01", "LINK_DACILOR_01", 90, 45, 11.5, 0.15, "signal"),
    ("Q_CLUJS_MART_N", "N_CLUJ_S", "LINK_MARTIRILOR_01", "LINK_MARTIRILOR_N_01", 90, 40, 11.5, 0.15, "stop"),
]


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


# ---------------------------------------------------------------------------
# Featured hotspots (§5). Target figures in CLAUDE.md are design goals; the
# figures the API returns are always computed live by the solver.
# ---------------------------------------------------------------------------

HOTSPOTS: list[dict[str, Any]] = [
    {
        "id": "HOTSPOT_CLUJ_EROILOR",
        "rank": 1,
        "linkId": "LINK_CLUJ_01",
        "codGis": "1042",
        "name": "Str. Cluj / Bd. Eroilor de la Tisa",
        "cartier": "Complexul Studențesc / Elisabetin",
        "baselineLanes": ["car", "car", "parking_blue"],
        "suggestedLanes": ["car", "bus", "bike"],
        "queueId": "Q_BRATIANU_SHARED",
        "stptLines": ["15", "16", "M11"],
        "bikeCorridor": "BIKE_CLUJ_JUSTITIEI",
        "dataBadge": "FIWARE Traffic Sensor · Cluj/Eroilor · Jul 2026",
        "center": [21.2349, 45.7444],
        "zoom": 15.2,
        "story_ro": "Traficul de scurtătură dinspre Calea Martirilor inundă Str. Cluj și saturează coada de la Podul Eroilor.",
        "story_en": "Selfish cut-through traffic from Calea Martirilor floods Str. Cluj and saturates the Podul Eroilor queue.",
    },
    {
        "id": "HOTSPOT_FERDINAND_CATEDRALA",
        "rank": 2,
        "linkId": "LINK_FERDINAND_01",
        "codGis": "0218",
        "name": "Bd. Regele Ferdinand I",
        "cartier": "Cetate",
        "baselineLanes": ["car", "car"],
        "suggestedLanes": ["car", "bus"],
        "queueId": "Q_3AUG_SHARED",
        "stptLines": ["E1", "E2", "33", "1", "2"],
        "bikeCorridor": "BIKE_CATEDRALA_TRAIAN",
        "dataBadge": "PMT Nomenclator Străzi · codGis #0218",
        "center": [21.2282, 45.7520],
        "zoom": 15.4,
        "story_ro": "Bulevardul din fața Catedralei servește drept scurtătură între Iosefin și Fabric.",
        "story_en": "The boulevard in front of the Cathedral acts as a shortcut between Iosefin and Fabric.",
    },
    {
        "id": "HOTSPOT_CIRCUMVALATIUNII",
        "rank": 3,
        "linkId": "LINK_CIRCUMVALATIUNII_01",
        "codGis": "0389",
        "name": "Calea Circumvalațiunii / Str. Gheorghe Lazăr",
        "cartier": "Circumvalațiunii",
        "baselineLanes": ["car", "car", "car"],
        "suggestedLanes": ["car", "car", "bike"],
        "queueId": "Q_LAZARE_SHARED",
        "stptLines": ["14", "40"],
        "bikeCorridor": "BIKE_DACIA_UNIRII",
        "dataBadge": "PMT Nomenclator Străzi · codGis #0389",
        "center": [21.2150, 45.7650],
        "zoom": 15.0,
        "story_ro": "Coada de la intersecția cu Str. Gh. Lazăr se formează din traficul de tranzit pe Circumvalațiunii.",
        "story_en": "The merge queue at Str. Gh. Lazăr is fed by through-traffic on Circumvalațiunii.",
    },
    {
        "id": "HOTSPOT_SESIZARI_IOSEFIN",
        "rank": 4,
        "linkId": "LINK_16DEC_01",
        "codGis": "0815",
        "name": "Bd. 16 Decembrie 1989 / Piața Iosefin",
        "cartier": "Iosefin",
        "baselineLanes": ["car", "car", "parking_red"],
        "suggestedLanes": ["car", "bus", "pedestrian_trees"],
        "queueId": "Q_CAROL_SHARED",
        "stptLines": ["E2", "33", "2"],
        "bikeCorridor": "BIKE_GARA_CATEDRALA",
        "dataBadge": "Sesizări API · Anonimizat GDPR · 19 rapoarte",
        "center": [21.2136, 45.7487],
        "zoom": 15.3,
        "story_ro": "Validat de 19 sesizări anonimizate: amestecul tramvai/autobuz/auto blochează Piața Maria.",
        "story_en": "Validated by 19 anonymised citizen reports: tram/bus/car mixing blocks Piața Maria.",
    },
]


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


# ---------------------------------------------------------------------------
# POIs (/api/mobile/pois) and events (/api/mobile/events)
# ---------------------------------------------------------------------------

POIS: list[dict[str, Any]] = [
    {"id": "catedrala-mitropolitana", "name": "Catedrala Mitropolitană", "category": "landmark", "coordinates": [21.2243, 45.7505]},
    {"id": "opera-nationala", "name": "Opera Națională Română", "category": "culture", "coordinates": [21.2262, 45.7545]},
    {"id": "piata-unirii", "name": "Piața Unirii", "category": "landmark", "coordinates": [21.2290, 45.7578]},
    {"id": "piata-victoriei", "name": "Piața Victoriei", "category": "landmark", "coordinates": [21.2253, 45.7527]},
    {"id": "bastionul-theresia", "name": "Bastionul Theresia", "category": "culture", "coordinates": [21.2340, 45.7565]},
    {"id": "muzeul-de-arta", "name": "Muzeul Național de Artă", "category": "culture", "coordinates": [21.2296, 45.7584]},
    {"id": "castelul-huniade", "name": "Castelul Huniade", "category": "culture", "coordinates": [21.2265, 45.7522]},
    {"id": "sinagoga-cetate", "name": "Sinagoga din Cetate", "category": "landmark", "coordinates": [21.2278, 45.7568]},
    {"id": "parcul-rozelor", "name": "Parcul Rozelor", "category": "park", "coordinates": [21.2330, 45.7500]},
    {"id": "parcul-justitiei", "name": "Parcul Justiției", "category": "park", "coordinates": [21.2302, 45.7444]},
    {"id": "parcul-botanic", "name": "Parcul Botanic", "category": "park", "coordinates": [21.2245, 45.7612]},
    {"id": "parcul-central", "name": "Parcul Central", "category": "park", "coordinates": [21.2215, 45.7530]},
    {"id": "universitatea-politehnica", "name": "Universitatea Politehnica Timișoara", "category": "education", "coordinates": [21.2300, 45.7470]},
    {"id": "universitatea-de-vest", "name": "Universitatea de Vest", "category": "education", "coordinates": [21.2310, 45.7475]},
    {"id": "stadion-dan-paltinisanu", "name": "Stadionul Dan Păltinișanu", "category": "sport", "coordinates": [21.2450, 45.7400]},
    {"id": "gara-de-nord", "name": "Gara Timișoara Nord", "category": "transport", "coordinates": [21.2068, 45.7506]},
    {"id": "piata-traian", "name": "Piața Traian", "category": "landmark", "coordinates": [21.2462, 45.7584]},
    {"id": "biserica-millenium", "name": "Biserica Millenium", "category": "landmark", "coordinates": [21.2468, 45.7578]},
    {"id": "iulius-town", "name": "Iulius Town", "category": "retail", "coordinates": [21.2287, 45.7668]},
    {"id": "piata-maria", "name": "Piața Maria (Biserica Reformată)", "category": "landmark", "coordinates": [21.2172, 45.7500]},
]

EVENTS: list[dict[str, Any]] = [
    {"id": "evt-poli-meci", "title": "SSU Poli Timișoara — meci de campionat", "venue": "Stadionul Dan Păltinișanu",
     "poiId": "stadion-dan-paltinisanu", "attractorNode": "N_COMPLEX", "start": "2026-11-21T18:00:00+02:00",
     "expectedAttendance": 9000, "coordinates": [21.2450, 45.7400]},
    {"id": "evt-concert-victoriei", "title": "Concert în Piața Victoriei", "venue": "Piața Victoriei",
     "poiId": "piata-victoriei", "attractorNode": "N_OPERA", "start": "2026-11-28T19:00:00+02:00",
     "expectedAttendance": 12000, "coordinates": [21.2253, 45.7527]},
    {"id": "evt-targ-craciun", "title": "Târgul de Crăciun Timișoara", "venue": "Piața Victoriei",
     "poiId": "piata-victoriei", "attractorNode": "N_CATEDRALA", "start": "2026-11-27T10:00:00+02:00",
     "expectedAttendance": 15000, "coordinates": [21.2255, 45.7535]},
]

# Event attractor uplift on OD pairs ending at the attractor node (event_rush preset).
EVENT_ATTRACTOR_UPLIFT = 1.35


# ---------------------------------------------------------------------------
# Timpark parking tariffs (€/h) + SMS short number
# ---------------------------------------------------------------------------

TIMPARK_TARIFFS_EUR_H = {"green": 0.91, "red": 0.61, "yellow": 0.42, "blue": 0.30}
TIMPARK_SMS = "7406"
TIMPARK_OCCUPANCY = 0.72  # peak-hour occupancy used for revenue estimates
CURB_SPACE_LENGTH_M = 5.5
EUR_TO_RON = 4.97


# ---------------------------------------------------------------------------
# Sesizări — already aggregated (GDPR: no descriptions, names or photos).
# ---------------------------------------------------------------------------

SESIZARI_AGGREGATES: dict[str, dict[str, Any]] = {
    "HOTSPOT_SESIZARI_IOSEFIN": {
        "radiusMeters": 500, "total": 19,
        "byCategory": {"Trafic rutier și semne de circulație": 11, "Străzi și trotuare": 6, "Transport public": 2},
        "byStatus": {"Inregistrata": 7, "In lucru": 8, "Finalizata": 4},
    },
    "HOTSPOT_CLUJ_EROILOR": {
        "radiusMeters": 500, "total": 12,
        "byCategory": {"Trafic rutier și semne de circulație": 7, "Străzi și trotuare": 3, "Transport public": 2},
        "byStatus": {"Inregistrata": 4, "In lucru": 5, "Finalizata": 3},
    },
    "HOTSPOT_FERDINAND_CATEDRALA": {
        "radiusMeters": 500, "total": 9,
        "byCategory": {"Trafic rutier și semne de circulație": 4, "Străzi și trotuare": 4, "Transport public": 1},
        "byStatus": {"Inregistrata": 3, "In lucru": 3, "Finalizata": 3},
    },
    "HOTSPOT_CIRCUMVALATIUNII": {
        "radiusMeters": 500, "total": 8,
        "byCategory": {"Trafic rutier și semne de circulație": 5, "Străzi și trotuare": 2, "Transport public": 1},
        "byStatus": {"Inregistrata": 2, "In lucru": 4, "Finalizata": 2},
    },
}


def sesizari_for_point(lng: float, lat: float, radius_m: float = 500) -> dict[str, Any]:
    """Deterministic aggregated counts for an arbitrary point (fallback)."""
    best = None
    for h in HOTSPOTS:
        d = haversine_m((lng, lat), tuple(h["center"]))
        if d <= radius_m * 1.6 and (best is None or d < best[0]):
            best = (d, h["id"])
    if best:
        agg = dict(SESIZARI_AGGREGATES[best[1]])
        agg["source"] = "seed"
        return agg
    seed = int(abs(lng * 10_000) + abs(lat * 10_000)) % 7
    total = 2 + seed
    a = max(1, total // 2)
    b = max(0, total - a - 1)
    return {
        "radiusMeters": int(radius_m), "total": total, "source": "seed",
        "byCategory": {"Trafic rutier și semne de circulație": a, "Străzi și trotuare": b, "Transport public": total - a - b},
        "byStatus": {"Inregistrata": total // 3, "In lucru": total // 3, "Finalizata": total - 2 * (total // 3)},
    }


# ---------------------------------------------------------------------------
# Air quality (data.primariatm.ro air-quality-forecast) — seed snapshot
# ---------------------------------------------------------------------------

AIR_QUALITY = [
    {"station": "Justiției", "coordinates": [21.2302, 45.7444], "pm10": 31.0, "pm25": 18.0, "no2": 38.0,
     "pollen": "scăzut", "aqiLabel": "Moderat"},
    {"station": "Parcul Botanic", "coordinates": [21.2245, 45.7612], "pm10": 22.0, "pm25": 12.0, "no2": 24.0,
     "pollen": "scăzut", "aqiLabel": "Bun"},
]

FIWARE_SENSOR = {
    "id": "urn:ngsi-ld:TrafficFlowObserved:cluj-eroilor-01",
    "name": "Cluj / Eroilor",
    # NGSI-LD convention used by the dataset is [lat, lng]; flipped when exported.
    "location_lat_lng": [45.7444, 21.2349],
    "intensity_veh_h_peak": 1180,
    "dateObserved": "2026-07",
}


# ---------------------------------------------------------------------------
# Cartiere (40 official neighbourhoods) — approximate polygons via clipped
# Voronoi tessellation of neighbourhood centroids.
# ---------------------------------------------------------------------------

CARTIERE_CENTROIDS: list[tuple[str, float, float]] = [
    ("Cetate", 21.2275, 45.7560), ("Iosefin", 21.2080, 45.7475), ("Elisabetin", 21.2235, 45.7430),
    ("Fabric", 21.2470, 45.7595), ("Complexul Studențesc", 21.2395, 45.7455), ("Circumvalațiunii", 21.2120, 45.7650),
    ("Dacia", 21.2225, 45.7735), ("Calea Aradului", 21.2330, 45.7740), ("Mehala", 21.1950, 45.7640),
    ("Ronaț", 21.1860, 45.7740), ("Calea Torontalului", 21.1990, 45.7740), ("Blașcovici", 21.2100, 45.7790),
    ("Ion Ionescu de la Brad", 21.2380, 45.7840), ("Tipografilor", 21.2420, 45.7750), ("Calea Lipovei", 21.2510, 45.7690),
    ("Bucovina", 21.2640, 45.7700), ("Kuntz", 21.2690, 45.7610), ("Calea Lugojului", 21.2710, 45.7520),
    ("Ciarda Roșie", 21.2730, 45.7390), ("Calea Buziașului", 21.2560, 45.7440), ("Calea Martirilor", 21.2430, 45.7330),
    ("Soarelui", 21.2380, 45.7230), ("Calea Girocului", 21.2260, 45.7280), ("Odobescu", 21.2320, 45.7365),
    ("Steaua", 21.2100, 45.7300), ("Fratelia", 21.1990, 45.7320), ("Calea Șagului", 21.2150, 45.7375),
    ("Freidorf", 21.1830, 45.7380), ("Plopi", 21.2760, 45.7710), ("Ghiroda Nouă", 21.2860, 45.7620),
    ("Badea Cârțan", 21.2400, 45.7655), ("Dâmbovița", 21.1980, 45.7460), ("Dorobanților", 21.1880, 45.7500),
    ("Modern", 21.2560, 45.7525), ("Popa Șapcă", 21.2190, 45.7335), ("Mircea cel Bătrân", 21.2040, 45.7390),
    ("Antenei", 21.2470, 45.7790), ("Kogălniceanu", 21.2190, 45.7820), ("Lunei", 21.2490, 45.7270),
    ("Aeroport Vest", 21.1760, 45.7620),
]

_ZONE_BBOX = (21.165, 45.712, 21.300, 45.795)


def _clip_polygon(poly: list[tuple[float, float]], bbox: tuple[float, float, float, float]) -> list[tuple[float, float]]:
    """Sutherland–Hodgman clip of a convex polygon to an axis-aligned bbox."""
    xmin, ymin, xmax, ymax = bbox

    def clip(points, inside, intersect):
        out = []
        for i, cur in enumerate(points):
            prev = points[i - 1]
            if inside(cur):
                if not inside(prev):
                    out.append(intersect(prev, cur))
                out.append(cur)
            elif inside(prev):
                out.append(intersect(prev, cur))
        return out

    def ix(x0):
        return lambda p, q: (x0, p[1] + (q[1] - p[1]) * (x0 - p[0]) / ((q[0] - p[0]) or 1e-12))

    def iy(y0):
        return lambda p, q: (p[0] + (q[0] - p[0]) * (y0 - p[1]) / ((q[1] - p[1]) or 1e-12), y0)

    pts = poly
    for inside, inter in (
        (lambda p: p[0] >= xmin, ix(xmin)), (lambda p: p[0] <= xmax, ix(xmax)),
        (lambda p: p[1] >= ymin, iy(ymin)), (lambda p: p[1] <= ymax, iy(ymax)),
    ):
        pts = clip(pts, inside, inter)
        if not pts:
            break
    return pts


def cartiere_geojson() -> dict[str, Any]:
    """40 approximate neighbourhood polygons as GeoJSON MultiPolygons ([lng, lat])."""
    import numpy as np
    from scipy.spatial import Voronoi

    pts = np.array([[lng, lat] for _, lng, lat in CARTIERE_CENTROIDS])
    xmin, ymin, xmax, ymax = _ZONE_BBOX
    # Mirror points across the bbox edges so every original region is bounded.
    mirrored = np.vstack([
        pts,
        np.column_stack([2 * xmin - pts[:, 0], pts[:, 1]]),
        np.column_stack([2 * xmax - pts[:, 0], pts[:, 1]]),
        np.column_stack([pts[:, 0], 2 * ymin - pts[:, 1]]),
        np.column_stack([pts[:, 0], 2 * ymax - pts[:, 1]]),
    ])
    vor = Voronoi(mirrored)
    features = []
    for idx, (name, lng, lat) in enumerate(CARTIERE_CENTROIDS):
        region = vor.regions[vor.point_region[idx]]
        if not region or -1 in region:
            continue
        poly = [tuple(vor.vertices[v]) for v in region]
        # order counter-clockwise around centroid
        cx = sum(p[0] for p in poly) / len(poly)
        cy = sum(p[1] for p in poly) / len(poly)
        poly.sort(key=lambda p: math.atan2(p[1] - cy, p[0] - cx))
        poly = _clip_polygon(poly, _ZONE_BBOX)
        if len(poly) < 3:
            continue
        ring = [[round(x, 6), round(y, 6)] for x, y in poly]
        ring.append(ring[0])
        features.append({
            "type": "Feature",
            "id": idx + 1,
            "properties": {"id": idx + 1, "name": name, "nameFaraDiacritice": strip_diacritics(name),
                           "centroid": [lng, lat], "source": "seed"},
            "geometry": {"type": "MultiPolygon", "coordinates": [[ring]]},
        })
    return {"type": "FeatureCollection", "features": features}


# ---------------------------------------------------------------------------
# Street register (Nomenclator) fallback
# ---------------------------------------------------------------------------

_EXTRA_STREETS: list[tuple[str, str, str, str]] = [
    # (codGis, denumire, tipStrada, cartier) — streets outside the simulated graph
    ("0100", "Piața Libertății", "Piață", "Cetate"),
    ("0103", "Str. Alba Iulia", "Stradă", "Cetate"),
    ("0104", "Str. Eugeniu de Savoya", "Stradă", "Cetate"),
    ("0105", "Str. Lucian Blaga", "Stradă", "Cetate"),
    ("0510B", "Bd. Vasile Pârvan", "Bulevard", "Elisabetin"),
    ("0905", "Str. Iosif Vulcan", "Stradă", "Iosefin"),
    ("1110", "Calea Bogdăneștilor", "Calea", "Calea Torontalului"),
    ("1120", "Bd. Simion Bărnuțiu", "Bulevard", "Complexul Studențesc"),
    ("1130", "Str. Paul Morand", "Stradă", "Calea Martirilor"),
    ("1140", "Bd. Iuliu Maniu", "Bulevard", "Dâmbovița"),
]


def _street_type(name: str) -> str:
    low = name.lower()
    if low.startswith("bd."):
        return "Bulevard"
    if low.startswith("calea"):
        return "Calea"
    if low.startswith("piața"):
        return "Piață"
    if low.startswith("splaiul"):
        return "Splai"
    if low.startswith("podul"):
        return "Pod"
    return "Stradă"


def nomenclator_streets() -> list[dict[str, Any]]:
    seen: dict[str, dict[str, Any]] = {}
    for tag, a, b, name, cod, lanes, speed, opts in SEGMENTS:
        if cod in seen:
            continue
        cartier = NODES[a][3]
        seen[cod] = {
            "codGis": cod,
            "denumireCompleta": name,
            "denumireCompletaFaraDiacritice": strip_diacritics(name),
            "tipStrada": _street_type(name),
            "cartier": cartier,
            "linkId": f"LINK_{tag}_01",
        }
    for cod, name, tip, cartier in _EXTRA_STREETS:
        seen.setdefault(cod, {
            "codGis": cod, "denumireCompleta": name,
            "denumireCompletaFaraDiacritice": strip_diacritics(name),
            "tipStrada": tip, "cartier": cartier, "linkId": None,
        })
    return sorted(seen.values(), key=lambda s: s["denumireCompletaFaraDiacritice"])


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
