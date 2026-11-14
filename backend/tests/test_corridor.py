"""Corridor model tests. Synthetic counts exist ONLY inside these tests (tmp dirs), never in data/."""
import csv
import random

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.corridor import config, model as model_mod
from app.corridor.assignment import LinkCosts, Network, _all_or_nothing, assign
from app.corridor.calibration import calibration_report, geh
from app.corridor.demand import furness
from app.corridor.inputs import SCHEMAS
from app.corridor.landuse import load_landuse
from app.corridor.model import CorridorModel, LaneChange, NeedsData
from app.corridor.osm_network import load_network
from app.corridor.scan import run_scan

MAIN = config.CORRIDOR.main_streets


# ---------------------------------------------------------------- solver
def test_textbook_braess_paradox_exact():
    """Braess (1968): 4000 drivers, 65 min without the shortcut, 80 min with it."""
    net = Network(4, [0, 1, 0, 2, 1], [1, 3, 2, 3, 2])
    c = LinkCosts(fixed=np.array([0, 45, 45, 0, 0.0]), k=np.array([1, 0, 0, 1, 0.0]),
                  cap=np.full(5, 100.0), beta=np.ones(5))
    with_cut = assign(net, c, [(0, 3, 4000.0)], rel_gap=1e-9)
    without = assign(net, c, [(0, 3, 4000.0)], usable=np.array([1, 1, 1, 1, 0], bool), rel_gap=1e-9)
    assert with_cut.od_time[(0, 3)] == pytest.approx(80.0, abs=1e-4)
    assert without.od_time[(0, 3)] == pytest.approx(65.0, abs=1e-4)


def test_wardrop_two_routes_bpr():
    net = Network(3, [0, 0, 2], [1, 2, 1])            # direct 0→1, detour 0→2→1
    c = LinkCosts(fixed=np.array([5.0, 3.0, 3.0]), k=np.array([0.75, 0.45, 0.45]),
                  cap=np.array([1000.0, 800, 800]), beta=np.full(3, 4.0))
    r = assign(net, c, [(0, 1, 2000.0)], rel_gap=1e-8)
    t = c.cost(r.flow)
    assert r.flow[0] > 0 and r.flow[1] > 0
    assert t[0] == pytest.approx(t[1] + t[2], rel=1e-4)


def _path_loading(net, cost, ods):
    """Reference: load each OD pair along its own shortest path, one pair at a time."""
    origins = sorted({o for o, _, _ in ods})
    _, pred = net.shortest_paths(cost, origins, np.ones(net.n_links, bool))
    row = {o: i for i, o in enumerate(origins)}
    y, ym = np.zeros(net.n_links), np.zeros(len(net.movements))
    for o, d, q in ods:
        path = net.path_links(pred[row[o]], d)
        for e in path:
            y[e] += q
        for a, b in zip(path[:-1], path[1:]):
            ym[net.movements[(a, b)]] += q
    return y, ym


def test_tree_loading_equals_path_loading():
    rng = random.Random(7)
    n = 30
    edges = {(i, i + 1) for i in range(n - 1)} | {(i + 1, i) for i in range(n - 1)}
    while len(edges) < 110:
        a, b = rng.randrange(n), rng.randrange(n)
        if a != b:
            edges.add((a, b))
    edges = sorted(edges)
    net = Network(n, [a for a, _ in edges], [b for _, b in edges])
    cost = np.array([rng.uniform(0.5, 3.0) for _ in edges])
    ods = [(rng.randrange(n), rng.randrange(n), rng.uniform(5, 50)) for _ in range(80)]
    ods = [(o, d, q) for o, d, q in ods if o != d]
    y, ym, _ = _all_or_nothing(net, cost, ods, np.ones(len(edges), bool))
    y2, ym2 = _path_loading(net, cost, ods)
    assert np.allclose(y, y2) and np.allclose(ym, ym2)


def test_banned_turn_forces_detour():
    """0→1→3 is fastest, but the turn (0→1) → (1→3) is banned: drivers must go 0→2→3."""
    links = [(0, 1), (1, 3), (0, 2), (2, 3)]
    cost = np.array([1.0, 1.0, 2.0, 2.0])
    free = Network(4, [a for a, _ in links], [b for _, b in links])
    banned = Network(4, [a for a, _ in links], [b for _, b in links], banned={(0, 1)})
    y, _, t = _all_or_nothing(free, cost, [(0, 3, 10.0)], np.ones(4, bool))
    assert t[(0, 3)] == pytest.approx(2.0) and list(y) == [10, 10, 0, 0]
    y, ym, t = _all_or_nothing(banned, cost, [(0, 3, 10.0)], np.ones(4, bool))
    assert t[(0, 3)] == pytest.approx(4.0) and list(y) == [0, 0, 10, 10]
    assert (0, 1) not in banned.movements and ym[banned.movements[(2, 3)]] == pytest.approx(10.0)


def test_furness_and_geh():
    t = {(a, b): 1.0 for a in "ABC" for b in "ABC"}
    m = furness({"A": 600, "B": 300, "C": 100}, {"A": 200, "B": 500, "C": 300}, t, beta=0.1)
    assert m.trips.sum(axis=1) == pytest.approx([600, 300, 100], rel=1e-5)
    assert geh(1000, 950) == pytest.approx(1.6, abs=0.05)
    assert geh(1500, 900) > 15


# ---------------------------------------------------------------- network + land use
def test_network_has_side_streets_and_gateways():
    net = load_network()
    classes = {l.highway for l in net.links}
    assert "residential" in classes
    assert 250 <= len(net.links) <= 800
    assert 10 <= len(net.gates) <= 24
    assert all(net.link(g.in_link or g.out_link).highway in config.GATEWAY_CLASSES for g in net.gates)
    for s in MAIN:
        assert s in {l.street for l in net.links}
    assert not any(l.speed_source.startswith("assumed") and "RO:urban" in l.speed_source for l in net.links)
    assert len(net.core_nodes) > 100


def test_osm_turn_restrictions_applied():
    m = CorridorModel()
    st = m.turn_stats
    assert st["applied"] >= 20 and st["uTurnsBanned"] > 0
    assert st["applied"] + st["skippedDisconnecting"] + st["outsideNetwork"] + st["viaWaySkipped"] <= st["relations"]
    assert all(mv not in m.solver_net.movements for mv in m.banned)
    assert m._connected(m.banned)


def test_landuse_zones_on_core_nodes():
    net, lu = load_network(), load_landuse()
    assert lu.summary["residents"] > 1000 and lu.summary["pois"] > 50
    assert 5 <= len(lu.zones) <= config.LANDUSE["max_zones"]
    assert all(z.node in net.core_nodes for z in lu.zones)


# ---------------------------------------------------------------- demand + model (no counts)
@pytest.fixture(scope="module")
def estimated():
    import tempfile
    from pathlib import Path

    return CorridorModel(input_dir=Path(tempfile.mkdtemp()))


def test_profiles_produce_balanced_demand(estimated):
    m = estimated
    tables = {p: m.od_table(p) for p in config.PROFILES}
    for p, od in tables.items():
        assert od.trips.sum() > 100, p
        assert od.summary["imbalancePct"] == pytest.approx(0, abs=1e-6)
        assert m.demand_source(p) == "estimated"
    assert tables["sunday"].summary["localTripsVehH"] < tables["morning"].summary["localTripsVehH"]
    nz = len(m.landuse.zones)
    o_morning = tables["morning"].trips[:nz].sum(axis=1)
    d_evening = tables["evening"].trips[:, :nz].sum(axis=0)
    assert np.corrcoef(o_morning, d_evening)[0, 1] > 0.9    # evening mirrors the morning


def test_solve_is_fast_and_conserves_flow(estimated):
    m = estimated
    m._cache.clear()
    base = m.solve([])
    assert base.rel_gap < 1e-4 and base.elapsed_ms < 3000
    # every inside node: flow in − flow out = trips ending there − trips starting there
    starts, ends = {}, {}
    for o, d, q in m.ods():
        starts[o] = starts.get(o, 0.0) + q
        ends[d] = ends.get(d, 0.0) + q
    for nid, node in m.net.nodes.items():
        if not node.inside:
            continue
        k = m.node_idx[nid]
        inflow = sum(base.flow[i] for i, l in enumerate(m.net.links) if l.to_node == nid)
        outflow = sum(base.flow[i] for i, l in enumerate(m.net.links) if l.from_node == nid)
        assert inflow - outflow == pytest.approx(ends.get(k, 0.0) - starts.get(k, 0.0), abs=1e-3)


def test_through_traffic_follows_time_of_day(estimated):
    m = estimated
    t = {p: m.od_table(p).summary["throughVehH"] for p in config.PROFILES}
    assert t["sunday"] < t["day"] < t["morning"] < t["evening"]
    ref = config.LANDUSE["through_reference_profile"]
    assert m.od_table(ref).summary["throughScale"] == pytest.approx(1.0)


def test_lane_change_and_closure(estimated):
    m = estimated
    cluj = max((l for l in m.net.links if l.street == "Strada Cluj"), key=lambda l: l.car_lanes)
    res = m.compare([LaneChange(cluj.id, cluj.car_lanes - 1, "bus")])
    assert res["demandSource"] == "estimated" and "braess" in res
    link = next(x for x in res["links"] if x["id"] == cluj.id)
    assert link["flowAfter"] <= link["flowBefore"] + 1e-6
    closed = m.compare([LaneChange(cluj.id, 0, "closed")])
    assert next(x for x in closed["links"] if x["id"] == cluj.id)["flowAfter"] == pytest.approx(0, abs=1e-6)
    assert all(len(r["pathAfter"]) >= 2 for r in closed["carRoutes"])


def test_warm_start_reaches_same_equilibrium(estimated):
    m = estimated
    lid = max((l for l in m.net.links if l.street == "Strada Cluj"), key=lambda l: l.car_lanes)
    ch = [LaneChange(lid.id, lid.car_lanes - 1, "bike")]
    costs, usable = m.costs(ch)
    cold = assign(m.solver_net, costs, m.ods(), usable=usable, rel_gap=1e-6, max_iter=2000)
    warm = m.solve(ch, rel_gap=1e-6, max_iter=2000)
    assert warm.total_time == pytest.approx(cold.total_time, rel=1e-4)


def test_scan_deterministic_and_flags_only_verified(estimated, tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CACHE_DIR", tmp_path)
    m = estimated
    m._cache.pop(("scan", "morning"), None)
    a = run_scan(m, "morning", workers=1, use_disk=False)
    m._cache.pop(("scan", "morning"), None)
    b = run_scan(m, "morning", workers=1, use_disk=False)
    assert [(r["street"], r["changePct"]) for r in a["rows"]] == [(r["street"], r["changePct"]) for r in b["rows"]]
    assert {r["kind"] for r in a["rows"]} == {"removal", "lane"}
    assert all(r["stage"] == "verified" for r in a["rows"] if r["braess"] or r["routeBraess"])
    assert a["tested"]["removal"] > 50
    # a verified row shows exactly what the user gets when applying it
    row = next(r for r in a["rows"] if r["stage"] == "verified" and r["kind"] == "removal")
    res = m.compare([LaneChange(i, 0, "closed") for i in row["linkIds"]])
    assert res["totals"]["changePct"] == pytest.approx(row["changePct"], abs=0.006)


# ---------------------------------------------------------------- calibration with counts
def _write(d, name, rows):
    with (d / name).open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=SCHEMAS[name])
        w.writeheader()
        for r in rows:
            w.writerow(r)


@pytest.fixture()
def counted(tmp_path):
    """TEST-ONLY morning counts: every gate 300 veh/h in and out (four 15-min intervals)."""
    net = load_network()
    rows = []
    for g in net.gates:
        for direction, ok in (("in", g.in_link), ("out", g.out_link)):
            if ok:
                for s, e in (("07:30", "07:45"), ("07:45", "08:00"), ("08:00", "08:15"), ("08:15", "08:30")):
                    rows.append({"gate_id": g.id, "direction": direction, "profile": "morning", "start": s, "end": e,
                                 "vehicles": 75, "source": "TEST", "notes": ""})
    _write(tmp_path, "gate_counts.csv", rows)
    return tmp_path


def test_gate_counts_calibrate_only_their_profile(counted):
    m = CorridorModel(input_dir=counted)
    assert m.demand_source("morning") == "calibrated" and m.demand_source("sunday") == "estimated"
    od = m.od_table("morning")
    gate_rows = [i for i, r in enumerate(od.rows) if r.kind == "gate"]
    assert od.trips[gate_rows].sum(axis=1) == pytest.approx([300.0] * len(gate_rows), rel=1e-4)


def test_link_counts_scale_local_demand(counted):
    m0 = CorridorModel(input_dir=counted)
    base = m0.solve([])
    busy = [l for i, l in sorted(enumerate(m0.net.links), key=lambda il: -base.flow[il[0]])
            if l.highway in config.SIDE_STREET_CLASSES][:2]
    target = {l.id: float(base.flow[m0.net.link_index[l.id]]) * 1.5 for l in busy}
    _write(counted, "link_counts.csv", [{"link_id": lid, "profile": "morning", "start": "07:30", "end": "08:30",
                                         "vehicles": round(v), "source": "TEST", "notes": ""} for lid, v in target.items()])
    m = CorridorModel(input_dir=counted)
    assert m.od_table("morning").summary["localMultiplier"] > 1.0
    res = m.solve([])
    got = sum(res.flow[m.net.link_index[lid]] for lid in target)
    assert got == pytest.approx(sum(target.values()), rel=0.15)


def test_calibration_report(counted, tmp_path):
    with pytest.raises(NeedsData):
        calibration_report(CorridorModel(input_dir=tmp_path / "none"))
    m0 = CorridorModel(input_dir=counted)
    (fi, fj), _ = next(iter(m0.solver_net.movements.items()))
    a, b = m0.net.links[fi], m0.net.links[fj]
    _write(counted, "turn_counts.csv", [{"node_id": a.to_node, "from_link_id": a.id, "to_link_id": b.id,
                                         "profile": "morning", "start": "07:30", "end": "08:30", "vehicles": 120,
                                         "source": "TEST"}])
    rep = calibration_report(CorridorModel(input_dir=counted))
    assert rep["summary"]["turnsCounted"] == 1 and rep["fitted"]["gates"]
    assert rep["demandSource"] == "calibrated"


# ---------------------------------------------------------------- API
def test_api_end_to_end(tmp_path, monkeypatch):
    from app.main import app

    monkeypatch.setattr(config, "INPUT_DIR", tmp_path / "empty")
    monkeypatch.setattr(config, "CACHE_DIR", tmp_path / "cache")
    monkeypatch.setenv("TMBG_SCAN_WORKERS", "1")
    monkeypatch.setattr(model_mod, "_MODEL", None)
    with TestClient(app) as c:
        net = c.get("/api/corridor").json()
        assert {p["id"] for p in net["profiles"]} == {"morning", "day", "evening", "sunday"}
        assert net["landUse"]["residents"] > 0 and net["zones"]["features"]
        lid = next(s for s in net["streets"] if s["street"] == "Strada Cluj")["directions"][0]["linkIds"][0]
        body = {"changes": [{"linkId": lid, "carLanesAfter": 1, "use": "bus"}], "profile": "sunday"}
        r = c.post("/api/corridor/simulate", json=body).json()
        assert r["status"] == "ok" and r["demandSource"] == "estimated" and r["profile"] == "sunday"
        assert c.get("/api/corridor/baseline", params={"profile": "evening"}).json()["profile"] == "evening"
        assert c.get("/api/corridor/demand", params={"profile": "day"}).json()["topPairs"]
        s = c.post("/api/corridor/sensitivity", json=body).json()
        assert [row["demandScale"] for row in s["rows"]] == [0.8, 1.0, 1.2]
        sc = c.get("/api/corridor/scan", params={"profile": "morning"}).json()
        assert sc["status"] == "ok" and sc["rows"]
        assert c.get("/api/corridor/calibration").json()["status"] == "needs_data"
