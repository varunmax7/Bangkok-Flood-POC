from pathlib import Path

import pytest
import yaml

from cctv.legal_gate import LegalGateError, require_go

SOURCE = "testsrc"


def _status_file(tmp_path: Path, entry: dict) -> Path:
    path = tmp_path / "legal_status.yaml"
    path.write_text(yaml.safe_dump({"sources": {SOURCE: entry}}))
    return path


def test_pending_raises(tmp_path):
    path = _status_file(
        tmp_path, {"decision": "PENDING", "approved_by": None, "approved_utc": None, "conditions_ack": False}
    )
    with pytest.raises(LegalGateError):
        require_go(SOURCE, path)


def test_no_go_raises_even_with_approver(tmp_path):
    path = _status_file(
        tmp_path,
        {"decision": "NO_GO", "approved_by": "alice", "approved_utc": "2026-10-07T00:00:00Z", "conditions_ack": True},
    )
    with pytest.raises(LegalGateError):
        require_go(SOURCE, path)


def test_go_without_approver_raises(tmp_path):
    path = _status_file(
        tmp_path, {"decision": "GO", "approved_by": None, "approved_utc": None, "conditions_ack": True}
    )
    with pytest.raises(LegalGateError):
        require_go(SOURCE, path)


def test_go_without_conditions_ack_raises(tmp_path):
    path = _status_file(
        tmp_path,
        {"decision": "GO", "approved_by": "alice", "approved_utc": "2026-10-07T00:00:00Z", "conditions_ack": False},
    )
    with pytest.raises(LegalGateError):
        require_go(SOURCE, path)


def test_full_go_passes(tmp_path):
    path = _status_file(
        tmp_path,
        {"decision": "GO", "approved_by": "alice", "approved_utc": "2026-10-07T00:00:00Z", "conditions_ack": True},
    )
    require_go(SOURCE, path)  # must not raise


def test_unknown_source_raises(tmp_path):
    path = _status_file(
        tmp_path,
        {"decision": "GO", "approved_by": "alice", "approved_utc": "2026-10-07T00:00:00Z", "conditions_ack": True},
    )
    with pytest.raises(LegalGateError):
        require_go("some_other_source", path)


def test_missing_status_file_raises(tmp_path):
    with pytest.raises(LegalGateError):
        require_go(SOURCE, tmp_path / "does_not_exist.yaml")


def test_real_legal_status_untouched_and_pending():
    """Guard against ever writing to the real gate file from code."""
    real = Path("cctv/legal_status.yaml")
    assert real.exists()
    sources = yaml.safe_load(real.read_text())["sources"]
    assert set(sources) == {"bmatraffic", "itic", "longdo", "dds_flood", "dds_scada"}
    for name, entry in sources.items():
        assert entry["decision"] == "PENDING", name
        assert entry["approved_by"] is None, name

    for src in sources:
        with pytest.raises(LegalGateError):
            require_go(src)  # default path -> the real file -> still PENDING
