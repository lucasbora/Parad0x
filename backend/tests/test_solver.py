import os

os.environ.setdefault("TMBG_OFFLINE", "1")

import numpy as np
import pytest

from app.engine.beckmann_solver import (
    PathSystem, beckmann_objective, delay_derivatives, delays, potentials, solve_equilibrium,
)
from app.engine.braess_detector import BraessEngine, LaneIntervention
from app.engine.extended_graph import EdgeParams, build_graph
from app.services import seed_timisoara as seed


@pytest.fixture(scope="module")
def engine():
    return BraessEngine()


def test_graph_size_matches_spec(engine):
    g = engine.graph
    assert 40 <= len(g.nodes) <= 50
    assert g.n_road >= 85
    assert len(g.queue_links) >= 24
    assert len(g.od_pairs) == 12
    for rl in g.road_links:  # WGS84 [lng, lat] around Timișoara
        for lng, lat in rl.coords:
            assert 21.15 < lng < 21.30 and 45.70 < lat < 45.80


def test_potentials_are_integrals_of_delays():
    p = EdgeParams(n_road=1, t0=np.array([2.0, 0.0]), cap=np.array([1800.0, 1.0]), a=np.array([0.15, 0.0]),
                   b=np.array([4.0, 1.0]), d0=np.array([11.5 / 60]), s=np.array([920.0]), alpha=np.array([0.18 / 60]))
    for zval in (0.0, 400.0, 920.0, 1500.0, 2600.0):
        z = np.array([zval, zval])
        h = 1e-3
        num = (potentials(z + h, p) - potentials(z - h, p)) / (2 * h) if zval > 0 else None
        if num is not None:
            assert np.allclose(num, delays(z, p), rtol=1e-5, atol=1e-7)
    # queue delay is continuous at s (β = d0 − α s)
    zs = np.array([0.0, 920.0])
    assert delays(zs, p)[1] == pytest.approx(11.5 / 60)
    assert delay_derivatives(np.array([0.0, 900.0]), p)[1] == 0.0


def test_burov_d0_and_saturation():
    from app.engine.extended_graph import QueueLink
    q = QueueLink("Q", "N", "A", "B", cycle_s=90, red_s=45, n_per_lane=11.5, alpha_s_per_vehh=0.18)
    assert q.d0_s() == pytest.approx(45 * 46 / 180)
    assert q.saturation(2) == pytest.approx(920.0)
    assert q.saturation(1) == pytest.approx(460.0)


def test_equilibrium_satisfies_wardrop_and_is_fast(engine):
    base = engine.baseline("morning_rush")
    res = base.result
    assert res.rel_gap < 1e-5
    assert res.elapsed_ms < 100.0
    # demand conservation
    for k in range(engine.system.n_od):
        s, n = engine.system.starts[k], engine.system.counts[k]
        assert res.x[s:s + n].sum() == pytest.approx(base.demand[k], rel=1e-9)
        used = res.x[s:s + n] > 1.0
        costs = res.path_cost[s:s + n]
        # Wardrop: all used routes have (nearly) equal, minimal cost
        assert costs[used].max() - costs.min() < 0.02
    assert np.all(res.x >= -1e-9)


def test_cfw_alone_converges_to_same_equilibrium(engine):
    base = engine.baseline("morning_rush")
    pure = solve_equilibrium(engine.system, base.params, base.demand, rel_gap=1e-4, max_iter=3000, polish=False)
    assert pure.rel_gap < 1e-4
    assert pure.total_time == pytest.approx(base.total_time, rel=2e-3)
    assert beckmann_objective(pure.z, base.params) >= base.result.objective - 1e-6 * base.result.objective


def test_cluj_eroilor_lane_swap_is_braess_negative(engine):
    h = next(h for h in seed.HOTSPOTS if h["id"] == "HOTSPOT_CLUJ_EROILOR")
    base = engine.baseline("morning_rush")
    sc = engine.evaluate("morning_rush", [LaneIntervention("LINK_CLUJ_01", ["car", "bus", "bike"])])
    v = sc.total_time - base.total_time
    assert v < 0, f"expected Braess improvement, got V={v}"
    # capacity scaled by m_car/m_orig and downstream queue saturation halved
    li = engine.graph.road_index["LINK_CLUJ_01"]
    assert sc.params.cap[li] == pytest.approx(base.params.cap[li] / 2)
    q_own = engine.graph.queue_index["Q_MV_CLUJ_PODUL"]
    assert sc.params.s[q_own] == pytest.approx(base.params.s[q_own] / 2)
    # the shared downstream queue at Podul Eroilor is relieved
    q = engine.graph.queue_index[h["queueId"]]
    nr = engine.graph.n_road
    assert sc.result.phi[nr + q] < base.result.phi[nr + q]
    assert sc.result.z[li] < base.result.z[li]


@pytest.mark.parametrize("hid", [h["id"] for h in seed.HOTSPOTS])
def test_all_featured_hotspots_have_negative_v(engine, hid):
    h = next(x for x in seed.HOTSPOTS if x["id"] == hid)
    base = engine.baseline("morning_rush")
    sc = engine.evaluate("morning_rush", [LaneIntervention(h["linkId"], h["suggestedLanes"])])
    assert sc.total_time - base.total_time < 0


def test_filter_cut_through_greedy_removal_never_worse(engine):
    base = engine.baseline("morning_rush")
    lanes = ["car", "bus", "bike"]
    plain = engine.evaluate("morning_rush", [LaneIntervention("LINK_CLUJ_01", lanes)])
    filt = engine.evaluate("morning_rush", [LaneIntervention("LINK_CLUJ_01", lanes, filter_cut_through=True)])
    assert filt.total_time <= plain.total_time + 1e-6
    assert filt.total_time < base.total_time
    assert filt.removed_paths, "greedy removal should filter the Cluj cut-through route"


def test_full_closure_removes_routes(engine):
    sc = engine.evaluate("morning_rush", [LaneIntervention("LINK_CLUJ_01", ["bus", "bike", "pedestrian_trees"])])
    li = engine.graph.road_index["LINK_CLUJ_01"]
    assert "LINK_CLUJ_01" in sc.closed_links
    assert sc.result.z[li] == pytest.approx(0.0, abs=1e-6)


def test_all_presets_solve(engine):
    for preset in ("morning_rush", "evening_rush", "now", "weekend", "event_rush"):
        b = engine.baseline(preset)
        assert b.total_time > 0
        assert b.result.rel_gap < 1e-4


def test_prescan_ranks_streets(engine):
    scan = engine.prescan("morning_rush")
    assert len(scan) > 10
    assert scan["LINK_CLUJ_01"]["V"] < 0


# ---------------------------------------------------------------------------
# Real OSM network (offline snapshot)
# ---------------------------------------------------------------------------

from app.seed import hotspots as _hotspots  # noqa: E402
from app.seed.osm_network import load_snapshot, snapshot_available  # noqa: E402

needs_snapshot = pytest.mark.skipif(not snapshot_available(), reason="OSM snapshot not built")


@pytest.fixture(scope="module")
def osm_graph():
    return build_graph(network="osm")


@needs_snapshot
def test_osm_snapshot_is_consistent():
    s = load_snapshot()
    node_ids = {n["id"] for n in s["nodes"]}
    assert len(node_ids) == len(s["nodes"]) > 1000
    link_ids = {l["id"] for l in s["links"]}
    assert len(link_ids) == len(s["links"])
    for l in s["links"]:
        assert l["from"] in node_ids and l["to"] in node_ids and l["from"] != l["to"]
        assert l["length_m"] > 0 and l["speed_kmh"] > 0
        assert "car" in l["lanes"] and set(l["lanes"]) <= {"car", "bus"}
        assert l["twin"] is None or l["twin"] in link_ids
    assert 0 < s["meta"]["n_signalized"] < len(s["nodes"])


@needs_snapshot
def test_osm_graph_keeps_frozen_interfaces(osm_graph):
    g = osm_graph
    table = g.node_table()
    assert len(table) == len(g.nodes)
    assert set(table[0]) == {"id", "name", "coordinates", "cartier"}
    n = table[len(table) // 2]
    assert g.snap_to_node(n["coordinates"][0] + 1e-6, n["coordinates"][1]) == n["id"]
    for rl in g.road_links:
        for lng, lat in rl.coords:
            assert 21.15 < lng < 21.30 and 45.70 < lat < 45.80


@needs_snapshot
def test_osm_graph_every_od_is_routable_and_solves(osm_graph):
    g = osm_graph
    counts = np.bincount([p.od_index for p in g.paths], minlength=len(g.od_pairs))
    assert (counts >= 1).all()
    system = PathSystem(g.incidence(), np.array([p.od_index for p in g.paths]), len(g.od_pairs))
    demand = np.full(len(g.od_pairs), 800.0)
    res = solve_equilibrium(system, g.base_params(), demand, rel_gap=1e-5)
    assert res.rel_gap < 1e-5
    assert np.allclose(np.bincount(system.od_of_path, weights=res.x), demand)


@needs_snapshot
def test_osm_hotspots_resolve_to_the_named_street_or_are_dropped(osm_graph):
    for h in _hotspots.HOTSPOTS:
        lid = _hotspots.resolve_link_id(osm_graph, h)
        if lid is not None:
            assert h["streetHint"] in osm_graph.link(lid).street_name.lower()
