import json
from pathlib import Path

import jsonschema
import pytest

from cctv.registry import build_registry as br

SCHEMA = json.loads(Path("cctv/registry/registry.schema.json").read_text())

EXAMPLE_CSV = (
    "source,source_cam_ref,name_th,name_en,lon,lat,loc_method,loc_accuracy_m,"
    "heading_deg,road_name,refresh_s,calib_refs,priority\n"
    "BMAT,ref1,ชื่อ1,Name 1,100.561,13.812,MAP_CLICK,20,180,Road A,120,,1\n"
    "ITIC,ref2,ชื่อ2,Name 2,100.590,13.840,MAP_CLICK,20,90,Road B,120,,2\n"
)


def test_fallback_to_fixtures_when_csv_missing(tmp_path):
    fc = br.build_registry(input_csv=tmp_path / "cameras_input.csv", output_path=tmp_path / "cameras.geojson")
    assert fc["metadata"]["is_mock"] is True
    assert (tmp_path / "cameras.geojson").exists()
    jsonschema.validate(fc, SCHEMA)


def test_csv_path_produces_valid_registry(tmp_path):
    csv_path = tmp_path / "cameras_input.csv"
    csv_path.write_text(EXAMPLE_CSV, encoding="utf-8")
    fc = br.build_registry(input_csv=csv_path, output_path=tmp_path / "cameras.geojson")
    assert fc["metadata"]["is_mock"] is False
    assert len(fc["features"]) == 2
    jsonschema.validate(fc, SCHEMA)
    cam_ids = [f["properties"]["cam_id"] for f in fc["features"]]
    assert cam_ids == ["BMAT-0001", "ITIC-0001"]


def test_unique_cam_ids_and_lonlat_sane(tmp_path):
    fc = br.build_registry(input_csv=tmp_path / "missing.csv", output_path=tmp_path / "cameras.geojson")
    cam_ids = [f["properties"]["cam_id"] for f in fc["features"]]
    assert len(cam_ids) == len(set(cam_ids))
    for f in fc["features"]:
        lon, lat = f["geometry"]["coordinates"]
        assert 90 < lon < 110  # EPSG:4326 lon/lat, Thailand range
        assert 5 < lat < 25


def test_no_url_like_strings_in_output(tmp_path):
    fc = br.build_registry(input_csv=tmp_path / "missing.csv", output_path=tmp_path / "cameras.geojson")
    for f in fc["features"]:
        for v in f["properties"].values():
            if isinstance(v, str):
                assert "http://" not in v.lower()
                assert "https://" not in v.lower()


def test_scrub_rejects_url_like_property():
    with pytest.raises(ValueError):
        br._scrub_no_urls({"source_cam_ref": "http://example.com/cam1"})


def test_csv_rejects_unknown_source(tmp_path):
    csv_path = tmp_path / "cameras_input.csv"
    csv_path.write_text(
        "source,source_cam_ref,name_th,name_en,lon,lat,loc_method,loc_accuracy_m,"
        "heading_deg,road_name,refresh_s,calib_refs,priority\n"
        "WEIRD,ref1,x,x,100.5,13.8,MAP_CLICK,20,0,Road,120,,1\n"
    )
    with pytest.raises(ValueError):
        br.build_registry(input_csv=csv_path, output_path=tmp_path / "cameras.geojson")


def test_select_for_archive_respects_cap_and_sort(tmp_path):
    fc = br.build_registry(input_csv=tmp_path / "missing.csv", output_path=tmp_path / "cameras.geojson")
    selected = br.select_for_archive(fc, n=3)
    assert len(selected) <= 3
    assert all(f["properties"]["in_domain"] for f in selected)
    assert all(f["properties"]["status"] == "ACTIVE" for f in selected)
    priorities = [f["properties"]["priority"] for f in selected]
    assert priorities == sorted(priorities)


def test_select_for_archive_default_cap_50():
    """Exercises the real `python -m cctv.registry.build_registry` path."""
    import tools.fixtures.make_fixtures as mf

    mf.main()
    fc = br.build_registry()
    selected = br.select_for_archive(fc)
    assert len(selected) <= 50
    assert Path("cctv/registry/cameras.geojson").exists()
    jsonschema.validate(fc, SCHEMA)
