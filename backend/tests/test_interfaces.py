"""Tests for the frozen team interfaces and the per-owner seed split."""
import copy

import pytest

from app.engine.braess_detector import BraessEngine
from app.engine.demand_model import ODDemand, build_od, od_demand
from app.seed import context, cycling, demand, hotspots, network, transit
from app.services import seed_timisoara as facade


@pytest.fixture(scope="module")
def graph():
    return BraessEngine().graph


def test_seed_facade_reexports_owner_modules():
    assert facade.NODES is network.NODES
    assert facade.OD_PAIRS is demand.OD_PAIRS
    assert facade.STPT_LINES is transit.STPT_LINES
    assert facade.OSM_CYCLEWAYS is cycling.OSM_CYCLEWAYS
    assert facade.POIS is context.POIS
    assert facade.HOTSPOTS is hotspots.HOTSPOTS


def test_build_od_interface(graph):
    ods = build_od(graph, "morning_rush")
    assert len(ods) == 12 and all(isinstance(o, ODDemand) for o in ods)
    node_ids = {n["id"] for n in graph.node_table()}
    for o in ods:
        assert o.origin_node in node_ids and o.destination_node in node_ids
        assert o.veh_h > 0
    assert sum(o.veh_h for o in ods) == pytest.approx(float(od_demand(graph, "morning_rush").sum()))


def test_node_table_and_snap(graph):
    table = graph.node_table()
    assert len(table) == len(graph.nodes)
    n = table[0]
    lng, lat = n["coordinates"]
    assert graph.snap_to_node(lng + 1e-5, lat - 1e-5) == n["id"]


def test_hotspots_resolve_by_location_without_link_ids(graph):
    resolved = {h["id"]: h["linkId"] for h in hotspots.resolve_hotspots(graph)}
    assert len(resolved) == 4
    for h in hotspots.HOTSPOTS:
        stripped = copy.deepcopy(h)
        stripped["linkId"] = "LINK_THAT_NO_LONGER_EXISTS"
        assert hotspots.resolve_link_id(graph, stripped) == resolved[h["id"]] == h["linkId"]
