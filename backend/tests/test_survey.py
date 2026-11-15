"""Citizen survey: parsing, shares, overrides. Synthetic answers live only in tmp_path."""
import csv

from fastapi.testclient import TestClient

from app.corridor import config, survey

HEADER = [
    "Marcaj de timp",
    "În ce cartier locuiți?",
    "Cât de des treceți prin zona Calea Martirilor / Strada Cluj?",
    "Dacă Primăria închide circulației o stradă laterală scurtă, ce se întâmplă cu traficul total din zonă?",
    "Cum ajungeți de obicei la serviciu sau la facultate?",
    "Când mergeți cu mașina, câte persoane sunt de obicei în ea (inclusiv dumneavoastră)?",
    "La ce oră plecați de obicei de acasă dimineața?",
    "Folosiți Waze sau Google Maps când conduceți prin oraș?",
    "Urmați scurtăturile prin străzi laterale pe care vi le sugerează aplicația?",
    "Vi se întâmplă să ocoliți Calea Martirilor sau Strada Cluj pe străzi laterale?",
    "Dacă da, pe ce străzi?",
    "Dacă o bandă dedicată ar face drumul dumneavoastră cu autobuzul mai rapid decât cu mașina, cu cât ar trebui să fie mai rapid ca să renunțați la mașină?",
]
DRIVER1 = ["t", "Iosefin", "Zilnic", "Se înrăutățește", "Conduc mașina", "1", "7:30–8:30", "Mereu", "Uneori", "Da",
           "Strada Cozia, Strada Craiova", "2 minute"]
DRIVER3 = ["t", "Fabric", "Zilnic", "Depinde", "Conduc mașina", "3 sau mai multe", "7:00–7:30", "Uneori", "Mereu", "Nu",
           "", "10 minute"]
PASSENGER = ["t", "Fabric", "Rar", "Rămâne la fel", "Sunt pasager într-o mașină", "2", "7:30–8:30", "Nu conduc",
             "Nu conduc", "Nu circul prin zonă", "Nu", "Nu am mașină"]
# cedilla ş/ţ (old Romanian keyboards) must read like the comma forms
WALKER = ["t", "Cetate", "Săptămânal", "Se înrăutăţeşte", "Pe jos", "Nu merg cu maşina", "După 8:30", "Nu conduc",
          "Nu conduc", "Nu", "", "Folosesc deja transportul public"]


def _write(path, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(HEADER)
        w.writerows(rows)


def test_summary_from_four_answers(tmp_path):
    _write(tmp_path / "a.csv", [DRIVER1, DRIVER3, PASSENGER, WALKER, [""] * len(HEADER)])
    s = survey.load(tmp_path)
    assert s["responses"] == 4
    assert s["carShare"]["k"] == 3 and s["carShare"]["share"] == 0.75
    occ = s["carOccupancy"]
    assert occ["n"] == 2 and occ["mean"] == 2.0          # drivers only: (1 + 3) / 2, passenger ignored
    assert s["routeChoice"]["usesNavApp"]["n"] == 2      # "Nu conduc" left out of the base
    assert s["routeChoice"]["avoidsCorridor"]["n"] == 3  # "Nu circul prin zonă" left out
    assert {x["answer"] for x in s["routeChoice"]["avoidStreetsMentioned"]} == {"Strada Cozia", "Strada Craiova"}
    assert s["closureBelief"]["expectsWorse"]["k"] == 2  # comma and cedilla spellings both counted
    assert s["departure"]["morningWindow"]["k"] == 2     # en-dash in "7:30–8:30"
    curve = {m: v["k"] for m, v in s["modeShift"]["curve"].items()}
    assert curve == {"2": 1, "5": 1, "10": 2, "15": 2}
    assert s["modeShift"]["asked"] == 2                  # transit user and no-car passenger → not asked
    assert survey.overrides(s) == {}                     # n < MIN_RESPONSES
    lo, hi = s["carShare"]["ci95"]
    assert 0 <= lo < 0.75 < hi <= 1


def test_overrides_need_enough_answers_and_can_be_switched_off(tmp_path, monkeypatch):
    _write(tmp_path / "a.csv", [DRIVER1] * 12)
    _write(tmp_path / "b.csv", [DRIVER3] * 8)            # files are combined
    s = survey.load(tmp_path)
    assert s["responses"] == 20 and len(s["files"]) == 2
    assert survey.overrides(s) == {"car_share": 1.0, "car_occupancy": 1.8}
    monkeypatch.setenv("TMBG_SURVEY", "0")
    assert survey.overrides(s) == {}


def test_share_switching_below_smallest_option(tmp_path):
    _write(tmp_path / "a.csv", [DRIVER1, DRIVER3, PASSENGER])
    s = survey.load(tmp_path)
    assert survey.share_switching(s, 0.24) == {"minutesFaster": 0.24, "k": 0, "n": 2, "share": 0.0,
                                               "belowSmallestOption": 2}
    assert survey.share_switching(s, 6)["option"] == 5


def test_no_answers(tmp_path):
    assert survey.load(tmp_path) is None
    assert survey.load(tmp_path / "missing") is None


def test_survey_endpoint_matches_model_inputs():
    from app.main import app

    r = TestClient(app).get("/api/corridor/survey")
    assert r.status_code == 200
    body = r.json()
    if body["status"] == "no_data":
        return
    for k in ("car_share", "car_occupancy"):
        assert body["usedInModel"][k]["value"] == config.LANDUSE[k]
    names = {x["streetInModel"] for x in body["avoidStreetsInModel"]}
    assert None not in names
