"""Field-data inputs (CSV files in backend/data/corridor/) and the data-status checklist.

Nothing in here invents a number. Demand is ESTIMATED from OpenStreetMap land use; counts are
optional and CALIBRATE it (gate + link counts) or CHECK it (turn counts + travel times, never
used for fitting). Every count row belongs to a time-of-day profile (morning / day / evening /
sunday, see config.PROFILES); a missing ``profile`` column means ``morning``.

Files (UTF-8 CSV, header row required):
  gate_counts.csv     gate_id,direction,profile,start,end,vehicles,source,notes        calibration
  link_counts.csv     link_id,profile,start,end,vehicles,source,notes                  calibration
  turn_counts.csv     node_id,from_link_id,to_link_id,profile,start,end,vehicles,source check (GEH)
  travel_times.csv    route,from_gate_id,to_gate_id,profile,start,minutes,source       check
  signal_timings.csv  node_id,approach_link_id,cycle_s,green_s,source                  replaces assumption
  lane_checks.csv     link_id,car_lanes,bus_lane,source                                replaces OSM
Reference lists generated from OSM (what/where to count): gates.csv, intersections.csv, links.csv
"""
from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.corridor import config
from app.corridor.config import DEFAULT_PROFILE, PROFILES
from app.corridor.osm_network import CorridorNetwork, compass

SCHEMAS: dict[str, list[str]] = {
    "gate_counts.csv": ["gate_id", "direction", "profile", "start", "end", "vehicles", "source", "notes"],
    "link_counts.csv": ["link_id", "profile", "start", "end", "vehicles", "source", "notes"],
    "turn_counts.csv": ["node_id", "from_link_id", "to_link_id", "profile", "start", "end", "vehicles", "source"],
    "travel_times.csv": ["route", "from_gate_id", "to_gate_id", "profile", "start", "minutes", "source"],
    "signal_timings.csv": ["node_id", "approach_link_id", "cycle_s", "green_s", "source"],
    "lane_checks.csv": ["link_id", "car_lanes", "bus_lane", "source"],
}
OPTIONAL_COLUMNS = {"profile", "notes"}

PURPOSE = {
    "gate_counts.csv": "Cars entering (in) and leaving (out) the area at each main-road gate. Replaces the "
                       "estimated through-traffic for that profile (calibration).",
    "link_counts.csv": "Cars per hour on a street inside the area (mid-block). Scales the estimated local "
                       "demand for that profile (calibration).",
    "turn_counts.csv": "Left/straight/right counts at 2–3 key intersections. Never used for fitting — only to "
                       "check the model (GEH).",
    "travel_times.csv": "GPS travel times between two gates. Never used for fitting — only to check the model.",
    "signal_timings.csv": "Cycle and green time per approach (stopwatch on video is fine). Otherwise a textbook "
                          "default is used and labelled as an assumption.",
    "lane_checks.csv": "Car lanes verified on site / Street View where OpenStreetMap is wrong or unsure.",
}
REQUIRED: set[str] = set()     # demand comes from land use; counts only improve / check it


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
        missing = [c for c in SCHEMAS[name] if c not in OPTIONAL_COLUMNS and c not in (reader.fieldnames or [])]
        if missing:
            raise InputError(f"{name}: missing columns {missing}")
        return [r for r in reader if any((v or "").strip() for v in r.values() if isinstance(v, str))]


def _profile(row: dict[str, str], fname: str) -> str:
    p = (row.get("profile") or "").strip() or DEFAULT_PROFILE
    if p not in PROFILES:
        raise InputError(f"{fname}: unknown profile {p!r} (use one of {', '.join(PROFILES)})")
    return p


@dataclass
class FieldData:
    gate_in: dict[str, dict[str, float]] = field(default_factory=dict)    # profile → gate → veh/h in
    gate_out: dict[str, dict[str, float]] = field(default_factory=dict)   # profile → gate → veh/h out
    gate_sources: dict[str, str] = field(default_factory=dict)
    link_counts: dict[str, dict[str, float]] = field(default_factory=dict)  # profile → link → veh/h
    turns: list[dict[str, Any]] = field(default_factory=list)
    travel_times: list[dict[str, Any]] = field(default_factory=list)
    signals: dict[tuple[str, str], tuple[float, float, str]] = field(default_factory=dict)
    lanes: dict[str, tuple[int, bool, str]] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def calibrated(self, profile: str) -> bool:
        return bool(self.gate_in.get(profile) or self.gate_out.get(profile) or self.link_counts.get(profile))


def _hourly(rows: list[dict[str, str]], key_fields: tuple[str, ...], fname: str, warnings: list[str]) -> dict:
    """Sum interval counts per (profile, key) and scale to veh/h if fewer than 60 minutes were counted."""
    acc: dict[tuple, list[float]] = {}
    for r in rows:
        try:
            dur = _minutes(r["end"]) - _minutes(r["start"])
            veh = float(r["vehicles"])
        except (ValueError, KeyError) as exc:
            raise InputError(f"{fname}: bad row {r} ({exc})") from exc
        if dur <= 0 or veh < 0:
            raise InputError(f"{fname}: bad interval/vehicles in row {r}")
        prof = _profile(r, fname)
        pr = PROFILES[prof]
        if not (_minutes(pr.start) - 30 <= _minutes(r["start"]) <= _minutes(pr.end) + 30):
            warnings.append(f"{fname}: {r['start']}–{r['end']} is outside the {prof} window {pr.start}–{pr.end}")
        key = (prof,) + tuple(r[k].strip() for k in key_fields)
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
    gates = {g.id: g for g in net.gates}

    rows = read_csv("gate_counts.csv", input_dir)
    for r in rows:
        gid = r["gate_id"].strip()
        if gid not in gates:
            raise InputError(f"gate_counts.csv: unknown gate_id {gid!r} (see gates.csv)")
        d = r["direction"].strip()
        if d not in ("in", "out"):
            raise InputError(f"gate_counts.csv: direction must be 'in' or 'out', got {d!r}")
        if (d == "in" and not gates[gid].in_link) or (d == "out" and not gates[gid].out_link):
            raise InputError(f"gate_counts.csv: gate {gid} has no '{d}' direction (see gates.csv counts_needed)")
        fd.gate_sources.setdefault(gid, r.get("source", "").strip())
    for (prof, gid, d), v in _hourly(rows, ("gate_id", "direction"), "gate_counts.csv", fd.warnings).items():
        (fd.gate_in if d == "in" else fd.gate_out).setdefault(prof, {})[gid] = v

    for (prof, lid), v in _hourly(read_csv("link_counts.csv", input_dir), ("link_id",), "link_counts.csv",
                                  fd.warnings).items():
        if lid not in net.link_index:
            raise InputError(f"link_counts.csv: unknown link {lid!r} (see links.csv)")
        fd.link_counts.setdefault(prof, {})[lid] = v

    for (prof, nid, fl, tl), v in _hourly(read_csv("turn_counts.csv", input_dir),
                                          ("node_id", "from_link_id", "to_link_id"), "turn_counts.csv",
                                          fd.warnings).items():
        for lid in (fl, tl):
            if lid not in net.link_index:
                raise InputError(f"turn_counts.csv: unknown link {lid!r} (see intersections.csv)")
        fd.turns.append({"profile": prof, "node_id": nid, "from_link_id": fl, "to_link_id": tl, "veh_h": v})

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
        fd.travel_times.append({**r, "profile": _profile(r, "travel_times.csv"), "minutes": float(r["minutes"])})

    for prof in PROFILES:
        gi, go = fd.gate_in.get(prof, {}), fd.gate_out.get(prof, {})
        if gi or go:
            missing = [g.id for g in net.gates if (g.in_link and g.id not in gi) or (g.out_link and g.id not in go)]
            if missing:
                fd.warnings.append(f"{prof}: {len(missing)} gate direction(s) not counted — they keep the "
                                   f"land-use estimate: {', '.join(missing)}")
    return fd


def data_status(net: CorridorNetwork, fd: FieldData, input_dir: Path | None = None) -> dict[str, Any]:
    d = input_dir or config.INPUT_DIR
    files = []
    for name in SCHEMAS:
        rows = read_csv(name, d) if (d / name).exists() else []
        files.append({"file": name, "present": bool(rows), "rows": len(rows), "required": name in REQUIRED,
                      "purpose": PURPOSE[name]})
    profiles = {}
    for prof in PROFILES:
        counted = set(fd.gate_in.get(prof, {})) | set(fd.gate_out.get(prof, {}))
        profiles[prof] = {
            "calibrated": fd.calibrated(prof),
            "gatesCounted": len(counted),
            "linkCounts": len(fd.link_counts.get(prof, {})),
            "turnCounts": sum(1 for t in fd.turns if t["profile"] == prof),
            "travelTimes": sum(1 for t in fd.travel_times if t["profile"] == prof),
        }
    return {
        # kept for the current UI: True once ANY profile has counts
        "ready": any(v["calibrated"] for v in profiles.values()),
        "demandSource": "calibrated" if any(v["calibrated"] for v in profiles.values()) else "estimated",
        "profiles": profiles,
        "files": files,
        "gatesCounted": max((v["gatesCounted"] for v in profiles.values()), default=0),
        "gatesTotal": len(net.gates),
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
