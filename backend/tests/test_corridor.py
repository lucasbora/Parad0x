"""Corridor model tests. Synthetic counts exist ONLY inside these tests (tmp dirs), never in data/."""
import csv

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.corridor import config, model as model_mod
from app.corridor.assignment import LinkCosts, Network, assign
from app.corridor.calibration import calibration_report, geh
from app.corridor.demand import furness
from app.corridor.inputs import SCHEMAS
from app.corridor.model import CorridorModel, LaneChange, NeedsData
from app.corridor.osm_network import load_network

MAIN = config.CORRIDOR.main_streets


# ---------------------------------------------------------------- solver benchmarks
def test_textbook_braess_paradox_exact():
    """Braess (1968) / Rapp example: 4000 drivers, 65 min without the shortcut, 80 min with it."""
    net = Network(4, [0, 1, 0, 2, 1], [1, 3, 2, 3, 2])
    c = LinkCosts(fixed=np.array([0, 45, 45, 0, 0.0]), k=np.array([1, 0, 0, 1, 0.0]),
                  cap=np.full(5, 100.0), beta=np.ones(5))
    with_cut = assign(net, c, [(0, 3, 4000.0)], rel_gap=1e-9)
    without = assign(net, c, [(0, 3, 4000.0)], usable=np.array([1, 1, 1, 1, 0], bool), rel_gap=1e-9)
    assert with_cut.od_time[(0, 3)] == pytest.approx(80.0, abs=1e-4)
    assert without.od_time[(0, 3)] == pytest.approx(65.0, abs=1e-4)


def test_wardrop_two_routes_bpr():
    """Two parallel BPR routes: equilibrium equalises travel times."""
    net = Network(3, [0, 0, 1, 2], [1, 2, 3 - 1, 1])  # 0→1 direct, 0→2→1 detour
    c = LinkCosts(fixed=np.array([5.0, 3.0, 0.0, 3.0]), k=np.array([0.75, 0.45, 0, 0.45]),
                  cap=np.array([1000.0, 800, 1e9, 800]), beta=np.full(4, 4.0))
    r = assign(net, c, [(0, 1, 2000.0)], rel_gap=1e-8)
    t_direct = c.cost(r.flow)[0]
    t_detour = c.cost(r.flow)[1] + c.cost(r.flow)[3]
    assert r.flow[0] > 0 and r.flow[1] > 0
    assert t_direct == pytest.approx(t_detour, rel=1e-4)


def test_furness_matches_counts():
    t = {(a, b): 1.0 for a in "ABC" for b in "ABC"}
    m = furness({"A": 600, "B": 300, "C": 100}, {"A": 200, "B": 500, "C": 300}, t, beta=0.1)
    assert m.trips.sum(axis=1) == pytest.approx([600, 300, 100], rel=1e-5)
    assert m.trips.sum(axis=0) == pytest.approx([200, 500, 300], rel=1e-5)
    assert m.trips[0, 0] == 0 and m.trips[1, 1] == 0  # no same-gate U-turn trips


def test_geh():
    assert geh(1000, 950) == pytest.approx(1.6, abs=0.05)
    assert geh(1500, 900) > 15


# ---------------------------------------------------------------- real OSM network
def test_network_built_from_osm_snapshot():
    net = load_network()
    assert 100 <= len(net.links) <= 400
    assert 8 <= len(net.gates) <= 20
    assert any(n.signalized for n in net.junctions)
    streets = {l.street for l in net.links}
    for s in MAIN:
        assert s in streets
    assert all(l.length_m > 0 and l.speed_kmh > 0 and l.car_lanes >= 1 for l in net.links)


def _write(d, name, rows):
    with (d / name).open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(SCHEMAS[name])
        w.writerows(rows)


@pytest.fixture()
def synthetic_inputs(tmp_path):
    """TEST-ONLY counts: every gate 300 veh/h in and out, in four 15-min intervals."""
    net = load_network()
    rows = []
    for g in net.gates:
        for direction, ok in (("in", g.in_link), ("out", g.out_link)):
            if ok:
                for start, end in (("07:30", "07:45"), ("07:45", "08:00"), ("08:00", "08:15"), ("08:15", "08:30")):
                    rows.append([g.id, direction, start, end, 75, "TEST", ""])
    _write(tmp_path, "gate_counts.csv", rows)
    return tmp_path


def test_needs_data_without_counts(tmp_path):
    m = CorridorModel(input_dir=tmp_path)
    assert m.status["ready"] is False
    with pytest.raises(NeedsData):
        m.compare([LaneChange(m.net.links[0].id, 0, "closed")])


def test_lane_change_on_cluj_runs_and_conserves_flow(synthetic_inputs):
    m = CorridorModel(input_dir=synthetic_inputs)
    assert m.status["ready"]
    cluj = [l for l in m.net.links if l.street == "Strada Cluj" and l.car_lanes >= 2]
    assert cluj, "Strada Cluj should have a multi-lane link in OSM"
    target = cluj[0]
    before = m.solve([])
    assert before.rel_gap < 1e-4
    assert before.elapsed_ms < 3000
    # flow conservation at every inside node
    for nid, node in m.net.nodes.items():
        if not node.inside:
            continue
        inflow = sum(before.flow[i] for i, l in enumerate(m.net.links) if l.to_node == nid)
        outflow = sum(before.flow[i] for i, l in enumerate(m.net.links) if l.from_node == nid)
        assert inflow == pytest.approx(outflow, abs=1e-3)
    res = m.compare([LaneChange(target.id, target.car_lanes - 1, "bus")])
    link = next(x for x in res["links"] if x["id"] == target.id)
    assert link["flowAfter"] <= link["flowBefore"] + 1e-6
    closed = m.compare([LaneChange(target.id, 0, "closed")])
    assert next(x for x in closed["links"] if x["id"] == target.id)["flowAfter"] == pytest.approx(0, abs=1e-6)
    assert closed["carRoutes"] and closed["trafficShifts"]


def test_calibration_report_with_turn_counts(synthetic_inputs):
    m0 = CorridorModel(input_dir=synthetic_inputs)
    (fi, fj), _ = next(iter(m0.solver_net.movements.items()))
    a, b = m0.net.links[fi], m0.net.links[fj]
    _write(synthetic_inputs, "turn_counts.csv", [[a.to_node, a.id, b.id, "07:30", "08:30", 120, "TEST"]])
    m = CorridorModel(input_dir=synthetic_inputs)
    rep = calibration_report(m)
    assert rep["summary"]["turnsCounted"] == 1
    assert rep["turns"][0]["geh"] >= 0


def test_api_needs_data_then_ok(tmp_path, synthetic_inputs, monkeypatch):
    from app.main import app

    monkeypatch.setattr(config, "INPUT_DIR", tmp_path / "empty")
    monkeypatch.setattr(model_mod, "_MODEL", None)
    with TestClient(app) as c:
        net = c.get("/api/corridor").json()
        assert net["dataStatus"]["ready"] is False
        lid = next(s for s in net["streets"] if s["street"] == "Strada Cluj")["directions"][0]["linkIds"][0]
        r = c.post("/api/corridor/simulate", json={"changes": [{"linkId": lid, "carLanesAfter": 1, "use": "bus"}]})
        assert r.json()["status"] == "needs_data"
        monkeypatch.setattr(config, "INPUT_DIR", synthetic_inputs)
        r = c.post("/api/corridor/simulate", json={"changes": [{"linkId": lid, "carLanesAfter": 1, "use": "bus"}]})
        body = r.json()
        assert body["status"] == "ok"
        assert body["totals"]["vehMinBefore"] > 0
        s = c.post("/api/corridor/sensitivity", json={"changes": [{"linkId": lid, "carLanesAfter": 1, "use": "bus"}]})
        assert [row["demandScale"] for row in s.json()["rows"]] == [0.8, 1.0, 1.2]


def test_test_mode_only_without_real_counts(tmp_path, synthetic_inputs):
    empty = CorridorModel(input_dir=tmp_path / "none")
    lid = next(l for l in empty.net.links if l.street == "Strada Cluj" and l.car_lanes >= 2)
    r = empty.compare([LaneChange(lid.id, lid.car_lanes - 1, "bike")], test=True)
    assert r["testData"] is True and r["totals"]["demandVehH"] > 0
    assert "braess" in r and r["braess"]["carCapacityRemoved"] is True
    b = empty.baseline(test=True)
    assert b["testData"] is True and all(x["timeSec"] >= x["freeTimeSec"] - 1e-6 for x in b["links"])
    real = CorridorModel(input_dir=synthetic_inputs)   # real counts present → test flag ignored
    assert real.compare([LaneChange(lid.id, lid.car_lanes - 1, "bike")], test=True)["testData"] is False
