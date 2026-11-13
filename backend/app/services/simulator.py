"""Orchestration layer between FastAPI and the engine: GeoJSON, metrics, briefs."""
from __future__ import annotations

import threading
from typing import Any

import numpy as np

from app import config
from app.engine.braess_detector import BraessEngine, LaneIntervention, Scenario, get_engine
from app.engine.extended_graph import CAR
from app.engine.route_recommender import RouteRecommender
from app.models import schemas
from app.services import green_scorer, live_data, osm_overpass, pmt_client
from app.services import seed_timisoara as seed

OWNERS = [
    "Direcția Generală de Investiții și Mentenanță (PMT)",
    "SMTT — Societatea Metropolitană de Transport Timișoara",
]
DECIDEM_URL = "https://decidem.primariatm.ro"
SESIZARI_URL = "https://sesizari.primariatm.ro"
MODE_SHIFT_SHARE = 0.15           # share of benefiting riders' car-equivalent trips that may shift
CAR_OCCUPANCY = 1.3
SHIFTED_TRIP_KM = 4.0


class Simulator:
    def __init__(self, engine: BraessEngine | None = None):
        self.engine = engine or get_engine()
        self.g = self.engine.graph
        self.routes = RouteRecommender(self.engine)
        self._network_cache: dict[str, dict] = {}
        self._hotspot_cache: dict[str, list[dict]] = {}
        self._lock = threading.Lock()
        self._lines_by_link: dict[str, list[str]] = {}
        for line in self.routes.lines:
            for li in line["links"]:
                self._lines_by_link.setdefault(self.g.road_links[li].id, []).append(line["shortName"])

    # ------------------------------------------------------------------ helpers
    def _parking_delta(self, interventions: list[LaneIntervention]) -> tuple[int, float, str | None]:
        spaces = 0
        revenue = 0.0
        zone = None
        tariffs = pmt_client.timpark_tariffs() if interventions else seed.TIMPARK_TARIFFS_EUR_H
        for iv in interventions:
            rl = self.g.link(iv.link_id)
            before = [l for l in rl.lanes if l.startswith("parking_")]
            after = [l for l in iv.new_lanes if l.startswith("parking_")]
            per_lane = int(rl.length_m // seed.CURB_SPACE_LENGTH_M)
            for z in set(before) | set(after):
                d = (after.count(z) - before.count(z)) * per_lane
                tariff = tariffs[z.split("_", 1)[1]]
                spaces += d
                revenue += d * tariff * seed.TIMPARK_OCCUPANCY
            zone = zone or (before[0].split("_", 1)[1] if before else None)
        return spaces, revenue, zone

    def metrics(self, sc: Scenario, base: Scenario, interventions: list[LaneIntervention] | None = None,
                riders: int = 0, gains: list[dict] | None = None) -> schemas.Metrics:
        eng = self.engine
        y, yb = sc.total_time, base.total_time
        v = y - yb
        co2_new, co2_base = eng.co2_kg_per_hour(sc), eng.co2_kg_per_hour(base)
        shift_co2 = 0.0
        for gain in gains or []:
            rel = (gain["oldMin"] - gain["newMin"]) / max(gain["oldMin"], 1e-6)
            line = next(l for l in seed.STPT_LINES if l["shortName"] == gain["shortName"])
            pax = line["frequencyPerHour"] * seed.VEHICLE_CAPACITY[line["type"]]
            cars = pax * MODE_SHIFT_SHARE * min(rel / 0.3, 1.0) / CAR_OCCUPANCY
            shift_co2 += cars * SHIFTED_TRIP_KM * 0.170
        spaces, revenue, _ = self._parking_delta(interventions or [])
        return schemas.Metrics(
            total_system_delay_veh_min=round(y, 1),
            braess_value_v=round(v, 1),
            delay_reduction_pct=round(-v / yb * 100.0, 2) if yb else 0.0,
            avg_intersection_queue_sec=round(eng.avg_queue_sec(sc), 1),
            co2_saved_kg_per_hour=round(co2_base - co2_new + shift_co2, 1) if interventions else 0.0,
            stpt_riders_benefiting_per_hour=riders,
            timpark_spaces_delta=spaces,
            timpark_hourly_revenue_delta_eur=round(revenue, 2),
            co2_kg_per_hour=round(co2_new, 1),
            solver_iterations=sc.result.iterations,
            solver_relative_gap=float(f"{sc.result.rel_gap:.2e}"),
            solver_ms=round(sc.result.elapsed_ms, 2),
        )

    def _link_props(self, sc: Scenario, i: int) -> dict[str, Any]:
        rl = self.g.road_links[i]
        lanes = sc.lane_overrides.get(rl.id, rl.lanes)
        z = float(sc.result.z[i])
        phi = float(sc.result.phi[i])
        cap = float(sc.params.cap[i])
        return {
            "flow": round(z, 1),
            "capacity": round(cap, 1),
            "vOverC": round(z / max(cap, 1.0), 3),
            "speedKmh": round(rl.length_m / 1000.0 / (phi / 60.0), 1) if phi > 0 else rl.speed_kmh,
            "travelTimeSec": round(phi * 60.0, 1),
            "bprDelaySec": round((phi - rl.t0_min) * 60.0, 1),
            "lanes": lanes,
        }

    def _queue_point(self, j: int) -> list[float]:
        q = self.g.queue_links[j]
        node = self.g.nodes[q.node]["coordinates"]
        frm = self.g.link(q.in_link).coords[0]
        t = 0.16
        return [round(node[0] + (frm[0] - node[0]) * t, 6), round(node[1] + (frm[1] - node[1]) * t, 6)]

    # ------------------------------------------------------------------ hotspots
    def hotspots(self, preset: str) -> list[dict]:
        with self._lock:
            if preset in self._hotspot_cache:
                return self._hotspot_cache[preset]
        base = self.engine.baseline(preset)
        out = []
        for h in seed.HOTSPOTS:
            ivs = [LaneIntervention(h["linkId"], h["suggestedLanes"])]
            sc = self.engine.evaluate(preset, ivs)
            q = self.g.queue_index[h["queueId"]]
            riders, gains = self.routes.line_gain_summary(base, sc)
            out.append({
                **{k: v for k, v in h.items() if not k.startswith("story")},
                "storyRo": h["story_ro"],
                "storyEn": h["story_en"],
                "streetName": self.g.link(h["linkId"]).street_name,
                "officialCodGis": live_data.official_streets(self.g).get(h["linkId"], {}).get("codGis"),
                "braessValueV": round(sc.total_time - base.total_time, 1),
                "delayReductionPct": round((base.total_time - sc.total_time) / base.total_time * 100, 2),
                "queueBeforeSec": round(float(base.result.phi[self.g.n_road + q]) * 60, 1),
                "queueAfterSec": round(float(sc.result.phi[self.g.n_road + q]) * 60, 1),
                "queueFlowBefore": round(float(base.result.z[self.g.n_road + q]), 0),
                "queueFlowAfter": round(float(sc.result.z[self.g.n_road + q]), 0),
                "saturationS": round(float(base.params.s[q]), 0),
                "linkFlow": round(float(base.result.z[self.g.road_index[h["linkId"]]]), 0),
                "stptRidersBenefitingPerHour": riders,
            })
        out.sort(key=lambda h: h["braessValueV"])
        with self._lock:
            self._hotspot_cache[preset] = out
        return out

    # ------------------------------------------------------------------ network
    def network(self, preset: str) -> dict[str, Any]:
        with self._lock:
            if preset in self._network_cache and preset != "now":
                return self._network_cache[preset]
        g = self.g
        base = self.engine.baseline(preset)
        scan = self.engine.prescan(preset)
        scores = green_scorer.score_links(g, base.result.z)
        hotspot_by_link = {h["linkId"]: h["id"] for h in seed.HOTSPOTS}
        official = live_data.official_streets(g)

        road_features = []
        for i, rl in enumerate(g.road_links):
            props = self._link_props(base, i)
            ps = scan.get(rl.id)
            mid = [(rl.coords[0][0] + rl.coords[-1][0]) / 2, (rl.coords[0][1] + rl.coords[-1][1]) / 2]
            ses = seed.sesizari_for_point(mid[0], mid[1], 500)
            v = round(ps["V"], 1) if ps else None
            imp = round(ps["I"], 2) if ps else None
            road_features.append({
                "type": "Feature",
                "id": i,
                "geometry": {"type": "LineString", "coordinates": rl.coords},
                "properties": {
                    "id": rl.id,
                    "codGis": official.get(rl.id, {}).get("codGis", rl.cod_gis),
                    "seedCodGis": rl.cod_gis,
                    "codGisSource": "PMT Nomenclator (live)" if rl.id in official else "seed",
                    "officialName": official.get(rl.id, {}).get("denumireCompleta"),
                    "streetName": rl.street_name,
                    "cartier": rl.cartier,
                    "direction": rl.id[-2:],
                    "twinId": rl.twin_id,
                    "fromName": g.nodes[rl.from_node]["name"],
                    "toName": g.nodes[rl.to_node]["name"],
                    "lengthM": round(rl.length_m, 0),
                    "freeFlowSpeedKmh": rl.speed_kmh,
                    "lanes": rl.lanes,
                    "baselineFlow": props["flow"],
                    "capacity": props["capacity"],
                    "vOverC": props["vOverC"],
                    "speedKmh": props["speedKmh"],
                    "travelTimeSec": props["travelTimeSec"],
                    "bprDelaySec": props["bprDelaySec"],
                    "braessValueV": v,
                    "braessImprovementPct": imp,
                    "prescanMode": ps["mode"] if ps else None,
                    "isBraessCandidate": bool(ps and ps["V"] < -0.5),
                    "isGreenOpportunity": bool(ps and abs(ps["I"]) < 0.5),
                    "greenSuitabilityScores": scores[rl.id],
                    "recommendedReallocation": green_scorer.recommend_reallocation(scores[rl.id]),
                    "timparkZone": rl.timpark_zone,
                    "cyclewayExisting": rl.cycleway,
                    "hotspotId": hotspot_by_link.get(rl.id),
                    "stptLines": sorted(set(self._lines_by_link.get(rl.id, []))),
                    "sesizariSummary": ses,
                },
            })

        queue_features = []
        for j, q in enumerate(g.queue_links):
            zq = float(base.result.z[g.n_road + j])
            s = float(base.params.s[j])
            queue_features.append({
                "type": "Feature",
                "id": j,
                "geometry": {"type": "Point", "coordinates": self._queue_point(j)},
                "properties": {
                    "id": q.id,
                    "intersectionName": g.nodes[q.node]["name"],
                    "inLinkId": q.in_link,
                    "outLinkId": q.out_link,
                    "control": q.control,
                    "flow": round(zq, 1),
                    "saturationS": round(s, 1),
                    "isSaturated": zq >= s,
                    "queueDelaySec": round(float(base.result.phi[g.n_road + j]) * 60.0, 1),
                    "d0Sec": round(q.d0_s(), 1),
                },
            })

        zones, zones_prov = pmt_client.get_zones()
        _, pois_prov = pmt_client.get_pois()
        _, events_prov = pmt_client.get_events()
        _, parking_prov = pmt_client.get_parking()
        pois = live_data.normalized_pois()
        events = live_data.normalized_events()
        lines_live = live_data.live_lines()
        transit, transit_prov = pmt_client.get_transit_network()
        cycling, cyc_prov = osm_overpass.get_cycling_layers()
        nomen, nomen_prov = pmt_client.get_nomenclator()

        def pt_features(items: list[dict], kind: str) -> list[dict]:
            feats = []
            for it in items:
                c = it.get("coordinates")
                if not c and "lat" in it and ("lng" in it or "lon" in it):
                    c = [it.get("lng", it.get("lon")), it["lat"]]
                if not c:
                    continue
                props = {k: v for k, v in it.items() if k != "coordinates"}
                props["kind"] = kind
                feats.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": c}, "properties": props})
            return feats

        stpt = []
        for l in seed.STPT_LINES:
            live = lines_live.get(l["shortName"], {})
            poly = (live.get("polylines") or {}).get(0)
            stpt.append({
                "type": "Feature",
                "geometry": {"type": "LineString",
                             "coordinates": poly or [g.nodes[n]["coordinates"] for n in l["nodes"]]},
                "properties": {"routeId": live.get("routeId", l["routeId"]), "shortName": l["shortName"],
                               "type": live.get("type", l["type"]), "color": live.get("color") or l["color"],
                               "headsign": l["headsign"], "longName": live.get("longName"),
                               "frequencyPerHour": l["frequencyPerHour"],
                               "geometrySource": "SMTT GTFS (live)" if poly else "schematic"},
            })
        cycleways = [{
            "type": "Feature",
            "geometry": {"type": "LineString", "coordinates": c["coordinates"]},
            "properties": {"id": c["id"], "name": c.get("name")},
        } for c in cycling["cycleways"]]
        timpark = live_data.timpark_features(g)
        sesizari = []
        for h in seed.HOTSPOTS:
            summ, _ = pmt_client.get_sesizari_summary(h["center"][1], h["center"][0], 500)
            sesizari.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": h["center"]},
                             "properties": {"hotspotId": h["id"], **summ}})
        air = pt_features(seed.AIR_QUALITY, "air_quality")
        sensor = {
            **{k: v for k, v in seed.FIWARE_SENSOR.items() if k != "location_lat_lng"},
            "coordinates": pmt_client.ngsi_point_to_lnglat(seed.FIWARE_SENSOR["location_lat_lng"]),
        }

        provenance = [p.as_dict() for p in (zones_prov, pois_prov, events_prov, transit_prov, cyc_prov, nomen_prov,
                                            parking_prov)]
        out = {
            "preset": preset,
            "roads": {"type": "FeatureCollection", "features": road_features},
            "queues": {"type": "FeatureCollection", "features": queue_features},
            "overlays": {
                "zones": zones,
                "stptLines": {"type": "FeatureCollection", "features": stpt},
                "osmCycleways": {"type": "FeatureCollection", "features": cycleways},
                "iveloStations": {"type": "FeatureCollection", "features": pt_features(cycling["iveloStations"], "ivelo")},
                "pois": {"type": "FeatureCollection", "features": pt_features(pois, "poi")},
                "events": {"type": "FeatureCollection", "features": pt_features(events, "event")},
                "timparkSegments": {"type": "FeatureCollection", "features": timpark},
                "sesizariClusters": {"type": "FeatureCollection", "features": sesizari},
                "airQuality": {"type": "FeatureCollection", "features": air},
            },
            "hotspots": self.hotspots(preset),
            "baselineMetrics": self.metrics(base, base).model_dump(by_alias=True),
            "odPairs": [
                {"id": od.id, "label": od.label, "demandVehH": round(float(base.demand[k]), 0)}
                for k, od in enumerate(g.od_pairs)
            ],
            "fiwareSensor": sensor,
            "feedVersion": transit.get("feedVersion", config.GTFS_FEED_VERSION),
            "timparkTariffsEurH": pmt_client.timpark_tariffs(),
            "fares": dict(zip(("ticketRon", "dayPassRon"), live_data.fares())),
            "osm": {"attribution": osm_overpass.ATTRIBUTION, "badge": osm_overpass.COMPLETENESS_BADGE},
            "stats": {
                "nodes": len(g.nodes), "roadLinks": g.n_road, "queueLinks": len(g.queue_links),
                "odPairs": len(g.od_pairs), "paths": len(g.paths),
                "braessCandidates": sum(1 for f in road_features if f["properties"]["isBraessCandidate"]),
                "prescanned": len(scan),
            },
            "provenance": provenance,
        }
        with self._lock:
            self._network_cache[preset] = out
        return out

    # ------------------------------------------------------------------ simulate
    def _queue_chart(self, base: Scenario, sc: Scenario, q: int) -> schemas.QueueChart:
        g = self.g
        ql = g.queue_links[q]
        d0 = float(base.params.d0[q]) * 60
        alpha = float(base.params.alpha[q]) * 60
        s0, s1 = float(base.params.s[q]), float(sc.params.s[q])
        z0, z1 = float(base.result.z[g.n_road + q]), float(sc.result.z[g.n_road + q])
        zmax = max(s0, s1, z0, z1) * 1.6 + 50

        def curve(s):
            pts = []
            for z in np.linspace(0, zmax, 41):
                val = d0 if z < s else alpha * z + (d0 - alpha * s)
                pts.append([round(float(z), 1), round(float(val), 2)])
            return pts

        return schemas.QueueChart(queue_id=ql.id, intersection_name=g.nodes[ql.node]["name"], d0_sec=round(d0, 2),
                                  saturation_s_before=round(s0, 1), saturation_s_after=round(s1, 1),
                                  alpha_sec_per_veh_h=round(alpha, 4), flow_before=round(z0, 1),
                                  flow_after=round(z1, 1), curve_before=curve(s0), curve_after=curve(s1))

    def _bpr_chart(self, base: Scenario, sc: Scenario, i: int) -> schemas.BprChart:
        rl = self.g.road_links[i]
        t0 = rl.t0_min * 60
        c0, c1 = float(base.params.cap[i]), float(sc.params.cap[i])
        z0, z1 = float(base.result.z[i]), float(sc.result.z[i])
        zmax = max(c0, z0, z1) * 1.5 + 50

        def curve(c):
            cc = max(c, 1.0)
            return [[round(float(z), 1), round(float(t0 * (1 + rl.a * (z / cc) ** rl.b)), 2)]
                    for z in np.linspace(0, zmax, 41)]

        return schemas.BprChart(link_id=rl.id, t0_sec=round(t0, 1), capacity_before=c0, capacity_after=c1,
                                flow_before=round(z0, 1), flow_after=round(z1, 1),
                                curve_before=curve(c0), curve_after=curve(c1 if c1 >= 1 else 1.0))

    def simulate(self, req: schemas.SimulateRequest) -> schemas.SimulateResponse:
        g = self.g
        ivs = [LaneIntervention(i.link_id, list(i.new_lane_allocation), i.filter_cut_through_route)
               for i in req.interventions]
        base = self.engine.baseline(req.preset)
        sc = self.engine.evaluate(req.preset, ivs) if ivs else base
        link_ids = [iv.link_id for iv in ivs]
        riders, gains = self.routes.line_gain_summary(base, sc) if ivs else (0, [])
        base_m = self.metrics(base, base)
        sim_m = self.metrics(sc, base, ivs, riders, gains)

        updated_links = []
        for i, rl in enumerate(g.road_links):
            p = self._link_props(sc, i)
            bf = float(base.result.z[i])
            updated_links.append(schemas.UpdatedLink(
                id=rl.id, flow=p["flow"], baseline_flow=round(bf, 1), delta_flow=round(p["flow"] - bf, 1),
                capacity=p["capacity"], v_over_c=p["vOverC"], speed_kmh=p["speedKmh"],
                travel_time_sec=p["travelTimeSec"], bpr_delay_sec=p["bprDelaySec"], lanes=p["lanes"]))
        updated_queues = []
        for j, q in enumerate(g.queue_links):
            zq, zb = float(sc.result.z[g.n_road + j]), float(base.result.z[g.n_road + j])
            s, sb = float(sc.params.s[j]), float(base.params.s[j])
            updated_queues.append(schemas.UpdatedQueue(
                id=q.id, intersection_name=g.nodes[q.node]["name"], flow=round(zq, 1), baseline_flow=round(zb, 1),
                saturation_s=round(s, 1), baseline_saturation_s=round(sb, 1), is_saturated=zq >= s,
                was_saturated=zb >= sb, queue_delay_sec=round(float(sc.result.phi[g.n_road + j]) * 60, 1),
                baseline_queue_delay_sec=round(float(base.result.phi[g.n_road + j]) * 60, 1),
                d0_sec=round(q.d0_s(), 1)))

        hotspot = next((h for h in seed.HOTSPOTS if h["linkId"] in link_ids), None)
        if ivs:
            car = self.routes.car_routes(base, sc, link_ids)
            stpt = self.routes.stpt_routes(base, sc, link_ids)
            bike = self.routes.bike_routes(base, sc, link_ids, preferred=hotspot["bikeCorridor"] if hotspot else None)
        else:
            car, stpt, bike = [], [], []

        # charts: hotspot's shared downstream queue, else the queue that changed most
        queue_chart = bpr_chart = None
        if ivs:
            if hotspot:
                qi = g.queue_index[hotspot["queueId"]]
            else:
                dz = np.abs(sc.result.z[g.n_road:] - base.result.z[g.n_road:])
                qi = int(np.argmax(dz))
            queue_chart = self._queue_chart(base, sc, qi)
            bpr_chart = self._bpr_chart(base, sc, g.road_index[link_ids[0]])

        spaces, revenue, zone = self._parking_delta(ivs)
        if zone is None and ivs:
            zone = g.link(link_ids[0]).timpark_zone
        eur_h = pmt_client.timpark_tariffs().get(zone) if zone else None
        ticket, day = live_data.fares()
        cost = schemas.CostComparison(
            stpt_ticket_ron=ticket, stpt_day_pass_ron=day, timpark_zone=zone, timpark_eur_per_hour=eur_h,
            timpark_ron_two_hours=round(eur_h * 2 * seed.EUR_TO_RON, 2) if eur_h else None,
            sms_number=seed.TIMPARK_SMS)

        ses = None
        prov = []
        if ivs:
            c = g.link(link_ids[0]).coords
            mid = [(c[0][0] + c[-1][0]) / 2, (c[0][1] + c[-1][1]) / 2]
            ses, sp = pmt_client.get_sesizari_summary(mid[1], mid[0], 500)
            prov.append(sp.as_dict())
        removed = []
        for r in sc.removed_paths:
            k = int(self.engine.od_of_path[r])
            removed.append(f"{g.od_pairs[k].id}_R{r - self.engine.system.starts[k] + 1}")

        return schemas.SimulateResponse(
            preset=req.preset, baseline_metrics=base_m, simulated_metrics=sim_m,
            updated_links=updated_links, updated_queues=updated_queues,
            recommended_routes=schemas.RecommendedRoutes(car_routes=car, stpt_routes=stpt, bike_routes=bike),
            cost_comparison=cost, queue_chart=queue_chart, bpr_chart=bpr_chart, sesizari_summary=ses,
            removed_route_ids=removed, closed_link_ids=sc.closed_links, provenance=prov,
        )

    # ------------------------------------------------------------------ Decidem
    def decidem_brief(self, req: schemas.DecidemBriefRequest) -> schemas.DecidemBriefResponse:
        sim = self.simulate(schemas.SimulateRequest(preset=req.preset, interventions=req.interventions))
        m = sim.simulated_metrics
        g = self.g
        official = live_data.official_streets(g)

        def cod(rl):
            return official.get(rl.id, {}).get("codGis", rl.cod_gis)

        streets = []
        cods = []
        for iv in req.interventions:
            rl = g.link(iv.link_id)
            cods.append(cod(rl))
            streets.append((rl, iv))
        lane_ro = {"car": "bandă auto", "bus": "bandă unică STPT", "bike": "pistă velo protejată",
                   "pedestrian_trees": "trotuar extins cu arbori"}
        lane_en = {"car": "car lane", "bus": "STPT bus lane", "bike": "protected bike lane",
                   "pedestrian_trees": "widened sidewalk with trees"}

        def lanes_txt(lanes, d):
            return ", ".join(d.get(l, f"parcare Timpark ({l.split('_')[-1]})" if d is lane_ro else
                                   f"Timpark parking ({l.split('_')[-1]})") for l in lanes)

        preset_ro = {"morning_rush": "vârful de dimineață", "evening_rush": "vârful de seară", "now": "ora curentă",
                     "weekend": "weekend", "event_rush": "eveniment major"}[req.preset]
        preset_en = req.preset.replace("_", " ")
        stpt = sim.recommended_routes.stpt_routes
        bike = sim.recommended_routes.bike_routes
        car = [r for r in sim.recommended_routes.car_routes if r.role == "recommended_arterial"]
        ses = sim.sesizari_summary or {}
        names = "; ".join(f"{rl.street_name} (codGis {cod(rl)}, {rl.cartier})" for rl, _ in streets) or "—"

        ro = [f"# Propunere de realocare a spațiului stradal — {names}", "",
              f"**Inițiator tehnic:** simulator TM-BraessGreen (model Burov et al., echilibru Wardrop).",
              f"**Responsabili municipali:** {OWNERS[0]}; {OWNERS[1]}.", "",
              "## Intervenție propusă"]
        en = [f"# Street space reallocation proposal — {names}", "",
              "**Technical initiator:** TM-BraessGreen simulator (Burov et al. model, Wardrop equilibrium).",
              f"**Municipal owners:** {OWNERS[0]}; {OWNERS[1]}.", "",
              "## Proposed intervention"]
        for rl, iv in streets:
            ro.append(f"- {rl.street_name} (codGis **{cod(rl)}**, sens {g.nodes[rl.from_node]['name']} → "
                      f"{g.nodes[rl.to_node]['name']}): din [{lanes_txt(rl.lanes, lane_ro)}] în "
                      f"[{lanes_txt(iv.new_lane_allocation, lane_ro)}]"
                      + ("; filtrarea traseului de scurtătură din navigație" if iv.filter_cut_through_route else ""))
            en.append(f"- {rl.street_name} (codGis **{cod(rl)}**, direction {g.nodes[rl.from_node]['name']} → "
                      f"{g.nodes[rl.to_node]['name']}): from [{lanes_txt(rl.lanes, lane_en)}] to "
                      f"[{lanes_txt(iv.new_lane_allocation, lane_en)}]"
                      + ("; cut-through route filtered from navigation" if iv.filter_cut_through_route else ""))
        ro += ["", f"## Rezultate simulate ({preset_ro})",
               f"- Valoarea Braess V = **{m.braess_value_v:+.1f} veh·min/h** "
               f"({'reduce' if m.braess_value_v < 0 else 'crește'} timpul total de deplasare în rețea)",
               f"- Variația întârzierii totale: **{m.delay_reduction_pct:+.2f}%** (pozitiv = îmbunătățire)",
               f"- Coadă medie la intersecții: {sim.baseline_metrics.avg_intersection_queue_sec:.0f} s → "
               f"{m.avg_intersection_queue_sec:.0f} s",
               f"- CO₂ economisit: {m.co2_saved_kg_per_hour:.1f} kg/h; călători STPT avantajați: "
               f"{m.stpt_riders_benefiting_per_hour}/h",
               f"- Locuri Timpark: {m.timpark_spaces_delta:+d} (venit {m.timpark_hourly_revenue_delta_eur:+.2f} €/h)"]
        en += ["", f"## Simulated results ({preset_en})",
               f"- Braess value V = **{m.braess_value_v:+.1f} veh·min/h** "
               f"({'reduces' if m.braess_value_v < 0 else 'increases'} total network travel time)",
               f"- Total delay change: **{m.delay_reduction_pct:+.2f}%** (positive = improvement)",
               f"- Mean intersection queue: {sim.baseline_metrics.avg_intersection_queue_sec:.0f} s → "
               f"{m.avg_intersection_queue_sec:.0f} s",
               f"- CO₂ saved: {m.co2_saved_kg_per_hour:.1f} kg/h; STPT riders benefiting: "
               f"{m.stpt_riders_benefiting_per_hour}/h",
               f"- Timpark spaces: {m.timpark_spaces_delta:+d} (revenue {m.timpark_hourly_revenue_delta_eur:+.2f} €/h)"]
        if stpt:
            ro.append("- Linii STPT: " + ", ".join(
                f"{s.short_name} ({s.old_corridor_time_min:.1f} → {s.new_corridor_time_min:.1f} min)" for s in stpt))
            en.append("- STPT lines: " + ", ".join(
                f"{s.short_name} ({s.old_corridor_time_min:.1f} → {s.new_corridor_time_min:.1f} min)" for s in stpt))
        if bike:
            b = bike[0]
            ro.append(f"- Coridor velo {b.name}: {b.protected_pct_before:.0f}% → {b.protected_pct_after:.0f}% protejat, "
                      f"{len(b.ivelo_stations_on_route)} stații i'velo")
            en.append(f"- Cycling corridor {b.name}: {b.protected_pct_before:.0f}% → {b.protected_pct_after:.0f}% "
                      f"protected, {len(b.ivelo_stations_on_route)} i'velo stations")
        if car:
            ro.append("- Rute auto recomandate: " + "; ".join(f"{r.name} ({r.flow_share_pct:.0f}% din flux)" for r in car))
            en.append("- Recommended car routes: " + "; ".join(f"{r.name} ({r.flow_share_pct:.0f}% of flow)" for r in car))
        if ses:
            ro += ["", "## Sesizări cetățeni (anonimizat GDPR, rază 500 m)",
                   f"- Total: {ses.get('total', 0)} — " + ", ".join(f"{k}: {v}" for k, v in ses.get("byCategory", {}).items())]
            en += ["", "## Resident reports (GDPR-anonymised, 500 m radius)",
                   f"- Total: {ses.get('total', 0)} — " + ", ".join(f"{k}: {v}" for k, v in ses.get("byCategory", {}).items())]
        ro += ["", "## Pași următori",
               "1. Consultare publică pe Decidem Timișoara (" + DECIDEM_URL + ").",
               "2. Monitorizare sesizări pe " + SESIZARI_URL + " înainte/după pilot.",
               "3. Pilot temporar (marcaje + delimitatoare) 8 săptămâni, cu numărători FIWARE.",
               "", "_Notă: modelul folosește date seed calibrate unde API-urile PMT nu sunt disponibile; "
               "rezultatele sunt orientative și trebuie validate cu măsurători de teren._"]
        en += ["", "## Next steps",
               "1. Public consultation on Decidem Timișoara (" + DECIDEM_URL + ").",
               "2. Track resident reports on " + SESIZARI_URL + " before/after a pilot.",
               "3. Temporary 8-week pilot (markings + bollards) with FIWARE counts.",
               "", "_Note: where PMT APIs are unavailable the model uses calibrated seed data; results are "
               "indicative and must be validated with field measurements._"]
        return schemas.DecidemBriefResponse(
            title_ro=f"Realocare spațiu stradal: {names}", title_en=f"Street reallocation: {names}",
            brief_ro="\n".join(ro), brief_en="\n".join(en), decidem_url=DECIDEM_URL, sesizari_url=SESIZARI_URL,
            cod_gis=cods, owners=OWNERS, metrics=m)


_SIM: Simulator | None = None
_SIM_LOCK = threading.Lock()


def get_simulator() -> Simulator:
    global _SIM
    with _SIM_LOCK:
        if _SIM is None:
            _SIM = Simulator()
        return _SIM


def search_streets(q: str, limit: int = 12) -> list[dict]:
    """Diacritic-free street search over the PMT Nomenclator (+ network link mapping)."""
    streets, _ = pmt_client.get_nomenclator()
    sim = get_simulator()
    g = sim.g
    by_cod = {}
    by_name = {}
    for rl in g.road_links:
        if rl.id.endswith("_01"):
            by_cod.setdefault(rl.cod_gis, rl)
            by_name.setdefault(seed.strip_diacritics(rl.street_name).lower(), rl)
    needle = seed.strip_diacritics(q).lower().strip()
    out = []
    for s in streets:
        hay = (s.get("denumireCompletaFaraDiacritice") or seed.strip_diacritics(s["denumireCompleta"])).lower()
        if needle and needle not in hay and needle != str(s.get("codGis", "")).lower():
            continue
        rl = by_cod.get(str(s.get("codGis"))) or by_name.get(hay)
        item = {**s, "linkId": rl.id if rl else None}
        if rl:
            c = rl.coords
            item["center"] = [(c[0][0] + c[-1][0]) / 2, (c[0][1] + c[-1][1]) / 2]
        out.append(item)
    out.sort(key=lambda s: (s["linkId"] is None, len(s["denumireCompleta"])))
    return out[:limit]


def lane_car_count(lanes: list[str]) -> int:
    return sum(1 for l in lanes if l == CAR)
