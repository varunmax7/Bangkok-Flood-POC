"""Camera registry builder. See docs/VARUN_IMPLEMENTATION.md §6 T11.

Builds `cctv/registry/cameras.geojson` from a human-provided CSV
(`cctv/registry/cameras_input.csv`, HU2). Falls back to the T01 fixture
camera set (marked `is_mock: true`) when that CSV doesn't exist yet, so
nothing downstream blocks waiting on it.

Never includes snapshot URLs — those live in `secrets/cctv_urls.json`.
"""
from __future__ import annotations

import csv
import json
import math
from pathlib import Path

from shapely.geometry import Point, shape

DEFAULT_INPUT_CSV = Path("cctv/registry/cameras_input.csv")
DEFAULT_OUTPUT = Path("cctv/registry/cameras.geojson")
DEFAULT_FIXTURE = Path("tools/fixtures/out/cameras.geojson")
DEFAULT_POLYGON_CANDIDATES = (
    Path("configs/analysis_polygon.geojson"),
    Path("tools/fixtures/out/analysis_polygon.geojson"),
)
DDS_HOTSPOTS = Path("data/interim/obs/dds_hotspots.geojson")

VALID_SOURCES = ("BMAT", "ITIC", "LNGD")
_URL_TOKENS = ("http://", "https://", "www.")


def _load_polygon(polygon_path: Path | None = None):
    candidates = (polygon_path,) if polygon_path else DEFAULT_POLYGON_CANDIDATES
    for p in candidates:
        if p and Path(p).exists():
            fc = json.loads(Path(p).read_text())
            return shape(fc["features"][0]["geometry"])
    return None


def _nearest_dds(lon: float, lat: float, hotspots_path: Path = DDS_HOTSPOTS):
    if not hotspots_path.exists():
        return None, None
    fc = json.loads(hotspots_path.read_text())
    pt = Point(lon, lat)
    best_id, best_dist = None, math.inf
    for feat in fc.get("features", []):
        d = pt.distance(shape(feat["geometry"]))
        if d < best_dist:
            best_dist, best_id = d, feat.get("properties", {}).get("point_id")
    return (best_id, best_dist) if best_id is not None else (None, None)


def _scrub_no_urls(props: dict) -> None:
    for k, v in props.items():
        if isinstance(v, str) and any(tok in v.lower() for tok in _URL_TOKENS):
            raise ValueError(f"refusing to write a URL-like value in property {k!r}: {v!r}")


def _to_float_or_none(v):
    try:
        return float(v) if v not in (None, "") else None
    except ValueError:
        return None


def _to_int_or_none(v):
    try:
        return int(v) if v not in (None, "") else None
    except ValueError:
        return None


def build_from_csv(input_csv: Path, polygon_path: Path | None = None) -> dict:
    polygon = _load_polygon(polygon_path)
    counters: dict[str, int] = {}
    features = []
    with Path(input_csv).open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            src = (row.get("source") or "").strip()
            if src not in VALID_SOURCES:
                raise ValueError(f"unknown source {src!r} in {input_csv} (expected one of {VALID_SOURCES})")
            counters[src] = counters.get(src, 0) + 1
            cam_id = f"{src}-{counters[src]:04d}"
            lon, lat = float(row["lon"]), float(row["lat"])
            in_domain = bool(polygon is not None and polygon.contains(Point(lon, lat)))
            nearest_id, dist = _nearest_dds(lon, lat)

            props = {
                "cam_id": cam_id,
                "source": src,
                "source_cam_ref": row.get("source_cam_ref") or None,
                "name_th": row.get("name_th") or None,
                "name_en": row.get("name_en") or None,
                "lon": lon,
                "lat": lat,
                "loc_method": row.get("loc_method") or None,
                "loc_accuracy_m": _to_float_or_none(row.get("loc_accuracy_m")),
                "heading_deg": _to_float_or_none(row.get("heading_deg")),
                "road_name": row.get("road_name") or None,
                "refresh_s": _to_int_or_none(row.get("refresh_s")),
                "calib_refs": row.get("calib_refs") or None,
                "priority": _to_int_or_none(row.get("priority")) or 99,
                "in_domain": in_domain,
                "nearest_dds_point_id": nearest_id,
                "dist_dds_m": dist,
                "road_roi_px": None,
                "status": "ACTIVE",
                "is_mock": False,
            }
            _scrub_no_urls(props)
            features.append(
                {"type": "Feature", "geometry": {"type": "Point", "coordinates": [lon, lat]}, "properties": props}
            )
    return {"type": "FeatureCollection", "metadata": {"is_mock": False}, "features": features}


def build_registry(
    input_csv: Path = DEFAULT_INPUT_CSV,
    output_path: Path = DEFAULT_OUTPUT,
    fixture_path: Path = DEFAULT_FIXTURE,
    polygon_path: Path | None = None,
) -> dict:
    input_csv, fixture_path, output_path = Path(input_csv), Path(fixture_path), Path(output_path)

    if input_csv.exists():
        fc = build_from_csv(input_csv, polygon_path)
    else:
        if not fixture_path.exists():
            raise FileNotFoundError(
                f"no cameras_input.csv at {input_csv} and no fixtures at {fixture_path}; run `make fixtures` first"
            )
        fc = json.loads(fixture_path.read_text())
        fc.setdefault("metadata", {})["is_mock"] = True

    for feat in fc["features"]:
        _scrub_no_urls(feat["properties"])

    cam_ids = [f["properties"]["cam_id"] for f in fc["features"]]
    if len(cam_ids) != len(set(cam_ids)):
        raise ValueError("duplicate cam_id in registry output")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(fc, indent=1))
    return fc


def select_for_archive(fc: dict, n: int = 50) -> list[dict]:
    """In-domain, ACTIVE cameras, sorted by priority then distance to a DDS hotspot."""
    candidates = [
        f
        for f in fc["features"]
        if f["properties"].get("in_domain") and f["properties"].get("status") == "ACTIVE"
    ]

    def _key(f):
        p = f["properties"]
        priority = p.get("priority") if p.get("priority") is not None else 99
        dist = p.get("dist_dds_m")
        return (priority, dist if dist is not None else math.inf)

    candidates.sort(key=_key)
    return candidates[:n]


def main() -> None:
    fc = build_registry()
    selected = select_for_archive(fc)
    print(f"wrote {DEFAULT_OUTPUT} with {len(fc['features'])} cameras; {len(selected)} selectable for archive")


if __name__ == "__main__":
    main()
