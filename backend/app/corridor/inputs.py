"""Field-data inputs (CSV files in backend/data/corridor/) and the data-status checklist.

Nothing in here invents a number. If a file is missing or empty, the corresponding part
of the model either falls back to a documented textbook ASSUMPTION (signals, lanes) or the
results are blocked entirely (traffic counts).

Files (UTF-8 CSV, header row required):
  gate_counts.csv     gate_id,direction,start,end,vehicles,source,notes          REQUIRED
  turn_counts.csv     node_id,from_link_id,to_link_id,start,end,vehicles,source   calibration
  signal_timings.csv  node_id,approach_link_id,cycle_s,green_s,source            recommended
  lane_checks.csv     link_id,car_lanes,bus_lane,source                           recommended
  travel_times.csv    route,from_gate_id,to_gate_id,start,minutes,source         validation
Reference lists generated from OSM (what/where to count): gates.csv, intersections.csv, links.csv
"""
from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.corridor import config
from app.corridor.osm_network import CorridorNetwork, compass

SCHEMAS: dict[str, list[str]] = {
    "gate_counts.csv": ["gate_id", "direction", "start", "end", "vehicles", "source", "notes"],
    "turn_counts.csv": ["node_id", "from_link_id", "to_link_id", "start", "end", "vehicles", "source"],
    "signal_timings.csv": ["node_id", "approach_link_id", "cycle_s", "green_s", "source"],
    "lane_checks.csv": ["link_id", "car_lanes", "bus_lane", "source"],
    "travel_times.csv": ["route", "from_gate_id", "to_gate_id", "start", "minutes", "source"],
}

PURPOSE = {
    "gate_counts.csv": "Cars entering (in) and leaving (out) the area at every gate, morning peak hour. Without "
                       "these the model has no real demand and shows no results.",
    "turn_counts.csv": "Left/straight/right counts at 2–3 key intersections. Used only to check the model (GEH).",
    "signal_timings.csv": "Cycle and green time per approach (stopwatch on video is fine). Otherwise a textbook "
                          "default is used and labelled as an assumption.",
    "lane_checks.csv": "Car lanes verified on site / Street View where OpenStreetMap is wrong or unsure.",
    "travel_times.csv": "GPS travel times along the corridor and its alternative. Used only to check the model.",
}
REQUIRED = {"gate_counts.csv"}


class InputError(ValueError):
    pass


def _minutes(hhmm: str) -> int:
    h, m = hhmm.strip().split(":")
    return int(h) * 60 + int(m)


def read_csv(name: str, input_dir: Path | None = None) -> list[dict[str, str]]:
    path = (input_dir or config.INPUT_DIR) / name
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        missing = [c for c in SCHEMAS[name] if c not in (reader.fieldnames or [])]
        if missing:
            raise InputError(f"{name}: missing columns {missing}")
        return [r for r in reader if any((v or "").strip() for v in r.values())]


@dataclass
class FieldData:
    gate_in: dict[str, float] = field(default_factory=dict)     # gate_id → veh/h entering
    gate_out: dict[str, float] = field(default_factory=dict)    # gate_id → veh/h leaving
    gate_sources: dict[str, str] = field(default_factory=dict)
    turns: list[dict[str, Any]] = field(default_factory=list)
    signals: dict[tuple[str, str], tuple[float, float, str]] = field(default_factory=dict)
    lanes: dict[str, tuple[int, bool, str]] = field(default_factory=dict)
    travel_times: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _hourly(rows: list[dict[str, str]], key_fields: tuple[str, ...], fname: str, warnings: list[str]) -> dict:
    """Sum interval counts per key and scale to veh/h if fewer than 60 minutes were counted."""
    acc: dict[tuple, list[float]] = {}
    for r in rows:
        try:
            dur = _minutes(r["end"]) - _minutes(r["start"])
            veh = float(r["vehicles"])
        except (ValueError, KeyError) as exc:
            raise InputError(f"{fname}: bad row {r} ({exc})") from exc
        if dur <= 0 or veh < 0:
            raise InputError(f"{fname}: bad interval/vehicles in row {r}")
        key = tuple(r[k].strip() for k in key_fields)
        a = acc.setdefault(key, [0.0, 0.0])
        a[0] += veh
        a[1] += dur
    out = {}
    for key, (veh, dur) in acc.items():
        if dur < 60:
            warnings.append(f"{fname} {'/'.join(key)}: only {dur:.0f} min counted, scaled ×{60 / dur:.2f} to veh/h")
        out[key] = veh * 60.0 / dur
    return out


def load_field_data(net: CorridorNetwork, input_dir: Path | None = None) -> FieldData:
    fd = FieldData()
    gate_ids = {g.id for g in net.gates}

    rows = read_csv("gate_counts.csv", input_dir)
    for r in rows:
        if r["gate_id"].strip() not in gate_ids:
            raise InputError(f"gate_counts.csv: unknown gate_id {r['gate_id']!r} (see gates.csv)")
        if r["direction"].strip() not in ("in", "out"):
            raise InputError(f"gate_counts.csv: direction must be 'in' or 'out', got {r['direction']!r}")
    hourly = _hourly(rows, ("gate_id", "direction"), "gate_counts.csv", fd.warnings)
    for (gid, d), v in hourly.items():
        (fd.gate_in if d == "in" else fd.gate_out)[gid] = v
    for r in rows:
        fd.gate_sources.setdefault(r["gate_id"].strip(), r.get("source", "").strip())

    for (nid, fl, tl), v in _hourly(read_csv("turn_counts.csv", input_dir), ("node_id", "from_link_id", "to_link_id"),
                                    "turn_counts.csv", fd.warnings).items():
        for lid in (fl, tl):
            if lid not in net.link_index:
                raise InputError(f"turn_counts.csv: unknown link {lid!r} (see intersections.csv)")
        fd.turns.append({"node_id": nid, "from_link_id": fl, "to_link_id": tl, "veh_h": v})

    for r in read_csv("signal_timings.csv", input_dir):
        lid = r["approach_link_id"].strip()
        if lid not in net.link_index:
            raise InputError(f"signal_timings.csv: unknown link {lid!r}")
        c, g = float(r["cycle_s"]), float(r["green_s"])
        if not (0 < g < c):
            raise InputError(f"signal_timings.csv: need 0 < green_s < cycle_s, got {g}/{c}")
        fd.signals[(r["node_id"].strip(), lid)] = (c, g, r.get("source", "").strip())

    for r in read_csv("lane_checks.csv", input_dir):
        lid = r["link_id"].strip()
        if lid not in net.link_index:
            raise InputError(f"lane_checks.csv: unknown link {lid!r}")
        fd.lanes[lid] = (int(r["car_lanes"]), r["bus_lane"].strip().lower() in ("yes", "da", "1", "true"),
                         r.get("source", "").strip())

    for r in read_csv("travel_times.csv", input_dir):
        fd.travel_times.append({**r, "minutes": float(r["minutes"])})

    missing_gates = [g.id for g in net.gates if (g.in_link and g.id not in fd.gate_in) or
                     (g.out_link and g.id not in fd.gate_out)]
    if fd.gate_in and missing_gates:
        fd.warnings.append(f"{len(missing_gates)} gate(s) without counts are treated as 0 veh/h: "
                           + ", ".join(missing_gates))
    return fd


def data_status(net: CorridorNetwork, fd: FieldData, input_dir: Path | None = None) -> dict[str, Any]:
    d = input_dir or config.INPUT_DIR
    files = []
    for name in SCHEMAS:
        rows = read_csv(name, d) if (d / name).exists() else []
        files.append({"file": name, "present": bool(rows), "rows": len(rows), "required": name in REQUIRED,
                      "purpose": PURPOSE[name]})
    counted = sorted(set(fd.gate_in) | set(fd.gate_out))
    countable = [g.id for g in net.gates]
    return {
        "ready": bool(fd.gate_in) and bool(fd.gate_out),
        "files": files,
        "gatesCounted": len(counted),
        "gatesTotal": len(countable),
        "warnings": fd.warnings,
        "inputDir": str(d),
    }


# ---------------------------------------------------------------------------
# Reference lists + empty templates (generated from OSM, never invented)
# ---------------------------------------------------------------------------

def write_reference_files(net: CorridorNetwork, input_dir: Path | None = None) -> list[Path]:
    d = input_dir or config.INPUT_DIR
    d.mkdir(parents=True, exist_ok=True)
    written = []

    def write(name: str, header: list[str], rows: list[list[Any]]) -> None:
        p = d / name
        with p.open("w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(header)
            w.writerows(rows)
        written.append(p)

    write("gates.csv", ["gate_id", "street", "side", "counts_needed", "lat", "lng", "google_maps"],
          [[g.id, g.street, g.side, "+".join(x for x, ok in (("in", g.in_link), ("out", g.out_link)) if ok),
            f"{g.lat:.6f}", f"{g.lng:.6f}", f"https://maps.google.com/?q={g.lat:.6f},{g.lng:.6f}"]
           for g in net.gates])
    rows = []
    for n in sorted(net.junctions, key=lambda n: (-n.signalized, n.name)):
        for li in [l for l in net.links if l.to_node == n.id]:
            for lo in [l for l in net.links if l.from_node == n.id and l.to_node != li.from_node]:
                rows.append([n.id, n.name, "yes" if n.signalized else "no", li.id,
                             f"{li.street} (heading {compass(li.bearing)})", lo.id,
                             f"{lo.street} (heading {compass(lo.bearing)})", f"{n.lat:.6f}", f"{n.lng:.6f}"])
    write("intersections.csv", ["node_id", "intersection", "signalized", "from_link_id", "from", "to_link_id", "to",
                                "lat", "lng"], rows)
    write("links.csv", ["link_id", "street", "heading", "length_m", "car_lanes_osm", "lanes_source", "speed_kmh",
                        "speed_source", "bus_lane_osm"],
          [[l.id, l.street, compass(l.bearing), round(l.length_m), l.car_lanes, l.lanes_source, l.speed_kmh,
            l.speed_source, "yes" if l.bus_lane else "no"] for l in net.links])
    for name, header in SCHEMAS.items():
        p = d / name
        if not p.exists():
            write(name, header, [])
    return written
