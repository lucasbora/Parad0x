"""Local effects, break-even, all-day and the greedy package (no counts; land-use demand)."""
import tempfile
from pathlib import Path

import pytest

from app.corridor import config, package
from app.corridor.model import CorridorModel, LaneChange
from app.corridor.osm_network import street_directions


@pytest.fixture(scope="module")
def m():
    return CorridorModel(input_dir=Path(tempfile.mkdtemp()))


def _street_links(m, name):
    return [l.id for l in m.net.links if l.street == name]


def test_compare_reports_local_effects(m):
    ids = _street_links(m, "Piața Tineretului")
    c = m.compare([LaneChange(i, 0, "closed") for i in ids], profile="morning")
    loc = c["local"]
    assert loc["sideStreetRelieved"]["street"] == "Piața Tineretului"
    assert loc["sideStreetRelieved"]["flowAfter"] == 0
    assert loc["vehHSavedPerHour"] == pytest.approx((c["totals"]["vehMinBefore"] - c["totals"]["vehMinAfter"]) / 60, abs=0.05)
    if loc["bestTrip"]:
        assert loc["bestTrip"]["minutesAfter"] < loc["bestTrip"]["minutesBefore"]
    assert "modeShift" in c


def test_break_even_restores_total(m):
    dirs = street_directions(m.net)
    lane = [LaneChange(i, m.car_lanes(i)[0] - 1, "bus") for i in dirs["Calea Martirilor 1989"]["S"] if m.car_lanes(i)[0] >= 2]
    b = m.break_even(lane, profile="morning")
    assert b["costPct"] > 0 and not b["free"]
    assert 0 < b["switchVehH"] < b["streetUsersVehH"] <= b["totalVehH"]
    # removing that share of the street's drivers brings total car time back to today's (or lower)
    assert b["switchShare"] < 0.2


def test_all_day_covers_every_profile(m):
    ids = _street_links(m, "Piața Tineretului")
    a = package.all_day(m, [LaneChange(i, 0, "closed") for i in ids])
    assert set(a) == set(config.PROFILES)
    assert a["morning"]["changePct"] < 0


def test_greedy_package_only_adds_steps_that_help(m, monkeypatch):
    rows = []
    for street in ("Piața Tineretului", "Strada Craiova"):
        rows.append({"kind": "removal", "braess": True, "street": street, "linkIds": _street_links(m, street),
                     "changePct": -0.2, "fromName": "", "toName": ""})
    monkeypatch.setattr(m, "scan", lambda profile: {"rows": rows})
    package._cache.clear()
    p = package.best_package(m, "morning")
    steps = p["filters"]["steps"]
    pcts = [s["cumulativeChangePct"] for s in steps]
    assert pcts == sorted(pcts, reverse=True) and pcts[0] < 0       # every step lowers the total further
    if p["withBus"]:
        assert p["withBus"]["changePct"] < 0                       # bus add-on kept only if still below today
    package._cache.clear()


def test_evaporation_removes_street_users_and_reports_staying_drivers(m):
    dirs = street_directions(m.net)
    lane = [LaneChange(i, m.car_lanes(i)[0] - 1, "bus") for i in dirs["Strada Cluj"]["S"] if m.car_lanes(i)[0] >= 2]
    plain = m.compare(lane, profile="morning")
    evap = m.compare(lane, profile="morning", evaporation=0.11)
    assert plain["evaporation"] is None
    e = evap["evaporation"]
    users = sum(q for o, d, q in m.ods(1.0, "morning") if (o, d) in m.street_users(lane, 1.0, "morning"))
    assert e["carsLeftVehH"] == pytest.approx(0.11 * users, abs=0.2)
    assert evap["totals"]["changePct"] < plain["totals"]["changePct"]      # fewer cars → lower total
    assert not evap["braess"]["detected"]                                  # never called a paradox
    assert e["stayingDriversChangePct"] is not None


def test_pmud_values_in_use_until_survey_is_large():
    if config.SURVEY and config.SURVEY["responses"] < 100:
        assert config.LANDUSE["car_share"] == config.LANDUSE["car_share_default"]
        assert "PMUD" in config.LANDUSE["car_share_source"]
