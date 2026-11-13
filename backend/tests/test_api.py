import os

os.environ.setdefault("TMBG_OFFLINE", "1")

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.pmt_client import sanitize_sesizari


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["feedVersion"] == "4.31-4"


def test_network_geojson(client):
    r = client.get("/api/network", params={"preset": "morning_rush"})
    assert r.status_code == 200
    body = r.json()
    roads = body["roads"]
    assert roads["type"] == "FeatureCollection"
    f = next(x for x in roads["features"] if x["properties"]["id"] == "LINK_CLUJ_01")
    p = f["properties"]
    for key in ("id", "codGis", "streetName", "cartier", "lanes", "baselineFlow", "capacity", "vOverC",
                "bprDelaySec", "braessValueV", "isBraessCandidate", "greenSuitabilityScores", "timparkZone",
                "sesizariSummary"):
        assert key in p
    assert p["codGis"] == "1042"
    assert p["isBraessCandidate"] is True
    assert set(p["greenSuitabilityScores"]) == {"bus", "bike", "trees"}
    assert f["geometry"]["type"] == "LineString"
    lng, lat = f["geometry"]["coordinates"][0]
    assert 21 < lng < 22 and 45 < lat < 46  # [lng, lat]
    q = body["queues"]["features"][0]["properties"]
    for key in ("id", "intersectionName", "flow", "saturationS", "isSaturated", "queueDelaySec", "d0Sec"):
        assert key in q
    ov = body["overlays"]
    assert len(ov["zones"]["features"]) == 40
    assert ov["zones"]["features"][0]["geometry"]["type"] == "MultiPolygon"
    for key in ("stptLines", "osmCycleways", "iveloStations", "pois", "events"):
        assert ov[key]["features"]
    assert len(ov["iveloStations"]["features"]) == 49
    assert len(ov["pois"]["features"]) == 20
    assert body["hotspots"][0]["braessValueV"] < 0


def test_simulate_cluj_bus_bike(client):
    payload = {"preset": "morning_rush", "interventions": [
        {"linkId": "LINK_CLUJ_01", "codGis": "1042", "newLaneAllocation": ["car", "bus", "bike"],
         "filterCutThroughRoute": True}]}
    r = client.post("/api/simulate", json=payload)
    assert r.status_code == 200, r.text
    body = r.json()
    sm = body["simulatedMetrics"]
    assert sm["braessValueV"] < 0
    assert sm["delayReductionPct"] > 0
    assert sm["timparkSpacesDelta"] < 0  # blue curb parking became a bike lane
    assert body["baselineMetrics"]["braessValueV"] == 0
    routes = body["recommendedRoutes"]
    roles = {c["role"] for c in routes["carRoutes"]}
    assert "throttled_braess_cut_through" in roles and "recommended_arterial" in roles
    for c in routes["carRoutes"]:
        assert len(c["coordinates"]) >= 2
    names = {s["shortName"] for s in routes["stptRoutes"]}
    assert {"15", "16", "M11"} <= names
    for s in routes["stptRoutes"]:
        if s["shortName"] in {"15", "16", "M11"}:
            assert s["newCorridorTimeMin"] < s["oldCorridorTimeMin"]
            assert s["ticketCostRon"] == 5
            assert len(s["nextDepartures"]) == 3
    bike = routes["bikeRoutes"][0]
    assert bike["routeId"] == "BIKE_CLUJ_JUSTITIEI"
    assert bike["protectedPctAfter"] > bike["protectedPctBefore"]
    assert body["queueChart"]["flowAfter"] < body["queueChart"]["flowBefore"]
    assert len(body["updatedLinks"]) > 85
    assert body["removedRouteIds"]


def test_simulate_validation(client):
    r = client.post("/api/simulate", json={"preset": "morning_rush", "interventions": [
        {"linkId": "NOPE", "newLaneAllocation": ["car"]}]})
    assert r.status_code == 404
    r = client.post("/api/simulate", json={"preset": "morning_rush", "interventions": [
        {"linkId": "LINK_CLUJ_01", "newLaneAllocation": ["helicopter"]}]})
    assert r.status_code == 422
    r = client.post("/api/simulate", json={"preset": "rush", "interventions": []})
    assert r.status_code == 422


def test_decidem_brief(client):
    r = client.post("/api/decidem-brief", json={"preset": "morning_rush", "interventions": [
        {"linkId": "LINK_CLUJ_01", "codGis": "1042", "newLaneAllocation": ["car", "bus", "bike"]}]})
    assert r.status_code == 200
    b = r.json()
    assert "1042" in b["briefRo"] and "1042" in b["briefEn"]
    assert "Direcția Generală de Investiții și Mentenanță" in b["briefRo"]
    assert "SMTT" in b["briefEn"]
    assert b["decidemUrl"] == "https://decidem.primariatm.ro"


def test_street_search_diacritic_free(client):
    r = client.get("/api/streets/search", params={"q": "circumvalatiunii"})
    assert r.status_code == 200
    res = r.json()["results"]
    assert any(x["codGis"] == "0389" and x["linkId"] == "LINK_CIRCUMVALATIUNII_01" for x in res)


def test_sesizari_gdpr_sanitizer_strips_personal_data():
    raw = [{"categorie": "Străzi și trotuare", "status": "In lucru", "descriere": "Ion Popescu ...",
            "nume": "Ion Popescu", "poze": ["https://x/y.jpg"], "email": "a@b.ro"},
           {"categorie": "Transport public", "status": "Finalizata", "telefon": "07..."}]
    out = sanitize_sesizari(raw)
    flat = repr(out)
    assert "Popescu" not in flat and "jpg" not in flat and "@" not in flat
    assert out["total"] == 2
    assert out["byCategory"]["Străzi și trotuare"] == 1
    assert out["byStatus"]["Finalizata"] == 1


def test_decode_polyline_and_street_normalisation():
    from app.services.live_data import normalize_street
    from app.services.pmt_client import decode_polyline

    # canonical example from the Google polyline spec
    pts = decode_polyline("_p~iF~ps|U_ulLnnqC_mqNvxq`@")
    assert pts == [[-120.2, 38.5], [-120.95, 40.7], [-126.453, 43.252]]
    assert normalize_street("Bd. Regele Ferdinand I") == normalize_street("Bulevardul Regele Ferdinand I")
    assert normalize_street("Calea Circumvalațiunii (Dacia)") == "calea circumvalatiunii"
