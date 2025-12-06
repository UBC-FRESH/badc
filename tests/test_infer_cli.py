from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from badc.cli.main import app

runner = CliRunner()


def test_infer_run_placeholder(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.csv"
    manifest.write_text(
        "recording_id,chunk_id,source_path,start_ms,end_ms,overlap_ms,sha256,notes\n"
        "rec1,chunk_a,data/audio/foo.wav,0,1000,0,hash,\n"
    )
    result = runner.invoke(app, ["infer", "run", str(manifest)])
    assert result.exit_code == 0


def test_infer_aggregate_placeholder() -> None:
    result = runner.invoke(
        app,
        [
            "infer",
            "aggregate",
            "chunk_a_detected",
            "chunk_a_detected",
            "chunk_b_detected",
        ],
    )
    assert result.exit_code == 0
    assert "chunk_a" in result.stdout
    assert "2 detections" in result.stdout
