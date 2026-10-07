import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

# pytest's package-rootdir insertion stops at tests/ (it has no __init__.py)
# since tests/varun does have one, so `import tools.fixtures...` /
# `import cctv...` etc. fail unless the repo root is also on sys.path.
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


@pytest.fixture
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture(autouse=True)
def _cwd_repo_root(monkeypatch):
    """All of Varun's modules use paths relative to the repo root."""
    monkeypatch.chdir(REPO_ROOT)


@pytest.fixture(autouse=True)
def _default_env(monkeypatch):
    """Keep tests hermetic: never fall through to a real .env."""
    monkeypatch.setenv("FG_CONTACT_EMAIL", "test@example.invalid")
    monkeypatch.setenv("FG_API_KEY_INGEST", "test-key")
    monkeypatch.setenv("FG_FRAMES_DIR", "dashboard/static/frames")
    monkeypatch.setenv("FG_SURROGATE_MODE", "mock")


@pytest.fixture
def tmp_data_dir(tmp_path, monkeypatch):
    """Redirect data/ writes into an isolated tmp dir for a single test."""
    d = tmp_path / "data"
    d.mkdir()
    return d
