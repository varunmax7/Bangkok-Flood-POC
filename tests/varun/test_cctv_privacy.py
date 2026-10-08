"""Privacy checks for CCTV frames (PDPA, Agent rule 6). See docs/VARUN_IMPLEMENTATION.md §6 T81.

Rule 6: frames are downscaled to <=640px and face/plate-blurred *before*
being written to disk; raw bytes are never persisted; the API only ever
serves blurred frames/thumbnails.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image
from starlette.routing import Mount

from dashboard.api.main import app
from tools.fixtures import make_fixtures as mf

IMAGE_GLOBS = ("*.jpg", "*.jpeg", "*.png")


def _all_images(root: Path):
    for pattern in IMAGE_GLOBS:
        yield from root.rglob(pattern)


def test_raw_frames_at_most_640px_wide():
    mf.main()
    images = list(_all_images(Path("data/cctv/raw")))
    assert images, "no raw frames found; run `make fixtures` first"
    for path in images:
        with Image.open(path) as img:
            assert img.width <= 640, f"{path} is {img.width}px wide (> 640)"


def test_thumbs_at_most_320px_wide():
    mf.main()
    images = list(_all_images(Path("data/cctv/thumbs")))
    assert images, "no thumbnails found; run `make fixtures` first"
    for path in images:
        with Image.open(path) as img:
            assert img.width <= 320, f"{path} is {img.width}px wide (> 320)"


def _static_mount_dirs() -> dict[str, str]:
    return {r.path: str(r.app.directory) for r in app.routes if isinstance(r, Mount) and hasattr(r.app, "directory")}


def test_api_never_mounts_a_raw_directory():
    """The API must serve blurred frames/thumbs only -- it must never expose
    a directory with "raw" in its path, since that's where this project's
    naming convention for downscaled-but-not-yet-thumbnailed frames lives
    (still privacy-processed, but not meant for direct API exposure)."""
    mounts = _static_mount_dirs()
    assert mounts, "expected at least the /frames and /thumbs static mounts"
    for route_path, directory in mounts.items():
        assert "raw" not in Path(directory).parts, f"{route_path} -> {directory} exposes a 'raw' directory"


def test_api_thumbs_mount_points_at_the_blurred_thumbs_dir():
    mounts = _static_mount_dirs()
    assert "/thumbs" in mounts
    assert Path(mounts["/thumbs"]).parts[-2:] == ("cctv", "thumbs")
