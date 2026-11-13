"""Road network seed: intersections, street segments and phantom queue movements.

OWNER: Rareș (engine). Replaced by the real OSM network import.
"""
from __future__ import annotations

from typing import Any


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
