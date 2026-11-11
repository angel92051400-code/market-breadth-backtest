import json
from pathlib import Path
from unittest.mock import patch

import check_source


def test_schedule_skips_unchanged_source(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    Path("docs").mkdir()
    Path("docs/summary.json").write_text(json.dumps({"source":{"source_sha256":"abc"}}))
    monkeypatch.setenv("GITHUB_EVENT_NAME","schedule")
    with patch.object(check_source,"upstream_hash",return_value="abc"):
        assert check_source.main() is False


def test_schedule_reruns_updated_source(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    Path("docs").mkdir()
    Path("docs/summary.json").write_text(json.dumps({"source":{"source_sha256":"abc"}}))
    monkeypatch.setenv("GITHUB_EVENT_NAME","schedule")
    with patch.object(check_source,"upstream_hash",return_value="new"):
        assert check_source.main() is True


def test_manual_always_runs_without_network(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GITHUB_EVENT_NAME","workflow_dispatch")
    with patch.object(check_source,"upstream_hash",side_effect=RuntimeError("should not poll")):
        assert check_source.main() is True


def test_missing_provenance_forces_backtest():
    assert check_source.should_run("schedule","any",None)
    assert check_source.should_run("schedule","abc","xyz")
    assert not check_source.should_run("schedule","abc","abc")
