"""Whole-network checks on the real corridor: the equations hold, inputs are read as intended and a
change in the lane editor really changes the result. Land-use demand only (no field counts)."""
import tempfile
from pathlib import Path

import numpy as np
import pytest

from app.corridor import config
from app.corridor.model import BASE_GAP, CorridorModel, LaneChange
from app.corridor.osm_network import load_network, street_directions


@pytest.fixture(scope="module")
def m():
    return CorridorModel(input_dir=Path(tempfile.mkdtemp()))


def _minus_one(m, street, heading, use="bus"):
    ids = street_directions(m.net)[street][heading]
    return [LaneChange(i, m.car_lanes(i)[0] - 1, use) for i in ids if m.car_lanes(i)[0] >= 2], ids


def _street_seconds(res, m, ids):
    return float(sum(res.cost[m.net.link_index[i]] for i in ids) * 60)


@pytest.mark.parametrize("profile", list(config.PROFILES))
def test_equilibrium_converged_and_total_is_flow_times_time(m, profile):
    res = m.solve([], profile=profile)
    assert res.rel_gap <= BASE_GAP * 1.01
    assert res.total_time == pytest.approx(float(np.dot(res.flow, res.cost)), rel=1e-9)
    assert (res.flow >= -1e-6).all()


def test_demand_totals_and_through_traffic(m):
    od = m.od_table("morning")
    assert sum(q for *_, q in m.ods(1.0, "morning")) == pytest.approx(od.trips.sum(), rel=1e-9)
    cap = m.costs([])[0].cap
    cin = sum(cap[m.net.link_index[g.in_link]] for g in m.net.gates if g.in_link)
    expected = config.LANDUSE["through_share_of_capacity"] * cin * m.through_scale("morning")
    assert od.summary["throughVehH"] == pytest.approx(expected, rel=0.01)
    # demand slider scales every trip
    assert sum(q for *_, q in m.ods(1.2, "morning")) == pytest.approx(1.2 * od.trips.sum(), rel=1e-9)


def test_osm_bus_lane_is_not_a_car_lane():
    net = load_network()
    cluj = [l for l in net.links if l.street == "Strada Cluj" and l.bus_lane]
    assert cluj, "Strada Cluj has a tagged bus lane"
    # tagged lanes=4 + lanes:psv=1 → 3 car lanes
    assert all(l.car_lanes == 3 and l.lanes_source == "osm (bus lane excluded)" for l in cluj)


def test_capacity_follows_lane_count(m):
    ch, _ = _minus_one(m, "Calea Martirilor 1989", "S")
    before, _ = m.costs([])
    after, _ = m.costs(ch)
    changed = {m.net.link_index[c.link_id]: c for c in ch}
    for i in range(len(m.net.links)):
        if i in changed:
            lanes0 = m.car_lanes(m.net.links[i].id)[0]
            assert after.cap[i] == pytest.approx(before.cap[i] * changed[i].car_lanes_after / lanes0)
        else:
            assert after.cap[i] == before.cap[i]


def test_link_cost_rises_with_flow_and_falls_with_capacity(m):
    c, _ = m.costs([])
    z = np.linspace(0, 3000, 7)
    for i in range(0, len(m.net.links), 37):
        times = [c.cost(np.full(len(m.net.links), v))[i] for v in z]
        assert all(b >= a for a, b in zip(times, times[1:]))
        assert times[0] == pytest.approx(c.fixed[i])
    # same flow, one lane less → slower
    ch, ids = _minus_one(m, "Strada Cluj", "S")
    c2, _ = m.costs(ch)
    flow = m.solve([]).flow
    for i in (m.net.link_index[x.link_id] for x in ch):
        assert c2.cost(flow)[i] > c.cost(flow)[i]


@pytest.mark.parametrize("street,heading", [("Calea Martirilor 1989", "S"), ("Strada Cluj", "S")])
def test_taking_a_lane_slows_that_street_and_the_zone(m, street, heading):
    ch, ids = _minus_one(m, street, heading)
    base, after = m.solve([], profile="morning"), m.solve(ch, profile="morning")
    assert _street_seconds(after, m, ids) > _street_seconds(base, m, ids)
    assert after.total_time > base.total_time


def test_closing_a_link_removes_all_its_traffic(m):
    lid = max(m.net.links, key=lambda l: m.solve([]).flow[m.net.link_index[l.id]] if l.street == "Strada Craiova" else -1).id
    res = m.solve([LaneChange(lid, 0, "closed")])
    assert res.flow[m.net.link_index[lid]] == pytest.approx(0.0, abs=1e-6)


def test_braess_on_the_real_network(m):
    """Closing the Piața Tineretului cut-through lowers total time in the morning peak."""
    ids = [l.id for l in m.net.links if l.street == "Piața Tineretului"]
    c = m.compare([LaneChange(i, 0, "closed") for i in ids], profile="morning")
    assert c["braess"]["detected"] and c["totals"]["changePct"] < -0.05


def test_bus_lane_skips_congestion(m, monkeypatch):
    """A bus on the new bus lane pays only the free time (+ red light); never more than before.
    Uses one synthetic line along the street: the live SMTT feed is not available offline."""
    from app.corridor import transit

    ch, ids = _minus_one(m, "Calea Martirilor 1989", "S")
    monkeypatch.setitem(m._cache, "lines", [{"shortName": "T", "routeId": "t", "type": 3, "color": "#000",
                                              "longName": "test", "direction": 0, "links": ids, "stops": []}])
    monkeypatch.setitem(m._cache, "free_fixed", m.costs([])[0].fixed)
    monkeypatch.setattr(transit, "buses_per_hour", lambda *a: (None, "test"))
    base, after = m.solve([], profile="morning"), m.solve(ch, profile="morning")
    b = m.bus_results(ch, base, after)[0]
    free = sum(m.costs([])[0].fixed[m.net.link_index[i]] for i in ids) * config.ASSUMPTIONS["bus_speed_factor"]
    assert b["usesChangedStreet"] and b["minutesAfter"] == pytest.approx(free, abs=0.006)
    assert b["minutesAfter"] <= b["minutesBefore"]


def test_more_evaporation_never_raises_total_time(m):
    ch, _ = _minus_one(m, "Strada Cluj", "S")
    totals = [m.compare(ch, profile="morning", evaporation=e)["totals"]["vehMinAfter"] for e in (0.0, 0.05, 0.11)]
    assert totals[0] >= totals[1] >= totals[2]
