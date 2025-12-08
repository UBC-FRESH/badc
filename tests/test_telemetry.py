from __future__ import annotations

from pathlib import Path

from badc import telemetry


def test_default_log_path_uses_manifest_stem(tmp_path, monkeypatch) -> None:
    manifest = Path("data/manifests/GNWT-290.csv")
    log_path = telemetry.default_log_path(
        manifest,
        base_dir=tmp_path,
        timestamp="20250101T000000Z",
    )
    assert log_path == tmp_path / "GNWT-290_20250101T000000Z.jsonl"
