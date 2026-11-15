"""Citizen survey (Google Forms export, anonymous: timestamp + neighbourhood only).

Every ``*.csv`` in ``backend/data/survey/`` is read and combined. Columns are found by keywords in
the normalised header, so a re-export with slightly different wording still loads.

Where an answer maps onto a model input (car share, people per car) it replaces the default once
there are enough answers (``overrides``); everything else is reported only. The mode-shift answers
are a STATED-preference indicator: the model has fixed demand and no mode choice, so they never
change demand.

This module must not import ``config`` (config imports it).
"""
from __future__ import annotations

import csv
import math
import os
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any

SURVEY_DIR = Path(__file__).resolve().parents[2] / "data" / "survey"
MIN_RESPONSES = 20
MIN_DRIVERS_FOR_OCCUPANCY = 5

# key → keywords that must ALL appear in the normalised header
COLUMNS: dict[str, tuple[str, ...]] = {
    "neighbourhood": ("cartier",),
    "frequency": ("cat de des", "martirilor"),
    "closure_belief": ("inchide", "strada laterala"),
    "mode": ("serviciu",),
    "occupancy": ("cate persoane",),
    "departure": ("ora", "plecati"),
    "nav_app": ("waze",),
    "follows_shortcuts": ("scurtatur",),
    "avoids_corridor": ("ocoliti",),
    "avoid_streets": ("pe ce strazi",),
    "mode_shift": ("mai rapid",),
}
MODE_SHIFT_MINUTES = (2, 5, 10, 15)


def norm(s: str | None) -> str:
    """Lower-case, no diacritics (comma and cedilla ș/ț alike), dashes → '-', single spaces."""
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.replace("–", "-").replace("—", "-").lower()
    return " ".join(s.split())


def _find_columns(header: list[str]) -> dict[str, int]:
    h = [norm(x) for x in header]
    out = {}
    for key, words in COLUMNS.items():
        for i, col in enumerate(h):
            if all(w in col for w in words):
                out[key] = i
                break
    return out


def read_rows(directory: Path | None = None) -> tuple[list[dict[str, str]], list[str]]:
    d = Path(directory) if directory else SURVEY_DIR
    rows: list[dict[str, str]] = []
    files: list[str] = []
    if not d.exists():
        return rows, files
    for path in sorted(d.glob("*.csv")):
        with path.open(encoding="utf-8-sig", newline="") as f:
            data = list(csv.reader(f))
        if not data:
            continue
        cols = _find_columns(data[0])
        n = 0
        for raw in data[1:]:
            if not any(x.strip() for x in raw):
                continue
            rows.append({k: (raw[i].strip() if i < len(raw) else "") for k, i in cols.items()})
            n += 1
        files.append(f"{path.name} ({n})")
    return rows, files


def wilson(k: int, n: int, z: float = 1.96) -> list[float] | None:
    """95 % Wilson score interval: correct for small samples, unlike p ± 1.96·√(p(1−p)/n)."""
    if n == 0:
        return None
    p = k / n
    den = 1 + z * z / n
    mid = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return [round(max(0.0, mid - half), 3), round(min(1.0, mid + half), 3)]


def share(k: int, n: int) -> dict[str, Any]:
    return {"k": k, "n": n, "share": round(k / n, 3) if n else None, "ci95": wilson(k, n)}


def _counts(rows: list[dict[str, str]], key: str) -> dict[str, int]:
    return dict(Counter(r.get(key, "") for r in rows if r.get(key, "")).most_common())


def _occupancy_value(ans: str) -> float | None:
    a = norm(ans)
    if a.startswith("3"):
        return 3.0          # "3 sau mai multe": lower bound
    if a in ("1", "2"):
        return float(a)
    return None


def _shift_threshold(ans: str) -> tuple[bool, float | None]:
    """(asked, threshold minutes). never → (True, None); already transit / no car → (False, None)."""
    a = norm(ans)
    if not a or "deja" in a or "nu am masina" in a:
        return False, None
    if "niciodata" in a:
        return True, None
    for m in MODE_SHIFT_MINUTES:
        if a.startswith(str(m)):
            return True, float(m)
    return False, None


def summarize(rows: list[dict[str, str]], files: list[str] | None = None) -> dict[str, Any]:
    n = len(rows)
    modes = [norm(r.get("mode", "")) for r in rows]
    drivers = sum("conduc" in m for m in modes)
    passengers = sum("pasager" in m for m in modes)

    # people per car, asked of DRIVERS only: each car has one driver, so this samples one answer per car
    occ = [v for r, m in zip(rows, modes) if "conduc" in m and (v := _occupancy_value(r.get("occupancy", ""))) is not None]
    occupancy = None
    if occ:
        mean = sum(occ) / len(occ)
        sd = math.sqrt(sum((x - mean) ** 2 for x in occ) / (len(occ) - 1)) if len(occ) > 1 else 0.0
        half = 1.96 * sd / math.sqrt(len(occ))
        occupancy = {"mean": round(mean, 3), "n": len(occ), "ci95": [round(mean - half, 2), round(mean + half, 2)],
                     "distribution": dict(Counter(int(x) for x in occ)),
                     "note": "drivers only; '3 or more' counted as 3 (lower bound)"}

    dep = [norm(r.get("departure", "")) for r in rows if r.get("departure")]
    nav = [norm(r.get("nav_app", "")) for r in rows if r.get("nav_app")]
    nav_base = [a for a in nav if "nu conduc" not in a]
    sc = [norm(r.get("follows_shortcuts", "")) for r in rows if r.get("follows_shortcuts")]
    sc_base = [a for a in sc if "nu conduc" not in a]
    av = [norm(r.get("avoids_corridor", "")) for r in rows if r.get("avoids_corridor")]
    av_base = [a for a in av if "nu circul" not in a]

    streets: Counter[str] = Counter()
    for r in rows:
        for part in (r.get("avoid_streets") or "").split(","):
            p = part.strip()
            if p and norm(p) not in ("nu", "-", "da"):
                streets[p] += 1

    beliefs = [norm(r.get("closure_belief", "")) for r in rows if r.get("closure_belief")]

    thresholds = [t for r in rows for asked, t in [_shift_threshold(r.get("mode_shift", ""))] if asked]
    asked = len(thresholds)
    curve = {str(m): share(sum(1 for t in thresholds if t is not None and t <= m), asked) for m in MODE_SHIFT_MINUTES}

    return {
        "responses": n,
        "files": files or [],
        "respondents": {"byNeighbourhood": _counts(rows, "neighbourhood"), "byFrequency": _counts(rows, "frequency")},
        "carShare": {**share(drivers + passengers, n), "drivers": drivers, "passengers": passengers},
        "carOccupancy": occupancy,
        "departure": {"counts": _counts(rows, "departure"),
                      "morningWindow": share(sum("7:30-8:30" in d for d in dep), len(dep))},
        "routeChoice": {
            "usesNavApp": share(sum(a in ("mereu", "uneori") for a in nav_base), len(nav_base)),
            "usesNavAppAlways": share(sum(a == "mereu" for a in nav_base), len(nav_base)),
            "followsShortcuts": share(sum(a in ("mereu", "uneori") for a in sc_base), len(sc_base)),
            "avoidsCorridor": share(sum(a == "da" for a in av_base), len(av_base)),
            "avoidStreetsMentioned": [{"answer": s, "count": c} for s, c in streets.most_common()],
        },
        "closureBelief": {"counts": _counts(rows, "closure_belief"),
                          "expectsWorse": share(sum("inrautat" in b for b in beliefs), len(beliefs)),
                          "expectsBetter": share(sum("imbunat" in b for b in beliefs), len(beliefs))},
        "modeShift": {"asked": asked, "never": sum(1 for t in thresholds if t is None), "curve": curve,
                      "note": "stated preference; excludes people who already use transit or have no car"},
    }


def load(directory: Path | None = None) -> dict[str, Any] | None:
    rows, files = read_rows(directory)
    return summarize(rows, files) if rows else None


def enabled() -> bool:
    return os.getenv("TMBG_SURVEY", "1") != "0"


def overrides(summary: dict[str, Any] | None) -> dict[str, float]:
    """Model inputs the survey replaces — only when switched on and with enough answers."""
    if not summary or not enabled() or summary["responses"] < MIN_RESPONSES:
        return {}
    out = {"car_share": summary["carShare"]["share"]}
    occ = summary.get("carOccupancy")
    if occ and occ["n"] >= MIN_DRIVERS_FOR_OCCUPANCY:
        out["car_occupancy"] = occ["mean"]
    return out


def share_switching(summary: dict[str, Any] | None, minutes_faster: float) -> dict[str, Any] | None:
    """Share of asked drivers who say they would switch at this time gain (largest option ≤ gain)."""
    if not summary:
        return None
    ms = summary["modeShift"]
    opts = [m for m in MODE_SHIFT_MINUTES if m <= minutes_faster]
    if not opts:
        return {"minutesFaster": round(minutes_faster, 2), "k": 0, "n": ms["asked"], "share": 0.0,
                "belowSmallestOption": MODE_SHIFT_MINUTES[0]}
    pt = ms["curve"][str(opts[-1])]
    return {"minutesFaster": round(minutes_faster, 2), "option": opts[-1], **pt}
