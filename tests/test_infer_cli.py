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
    result = runner.invoke(app, ["infer", "run", str(manifest), "--runner-cmd", "echo stub"])
    assert result.exit_code == 0
    assert "Processed 1 jobs" in result.stdout


def test_infer_aggregate_placeholder() -> None:
    detections_dir = Path("artifacts/infer_test")
    detections_dir.mkdir(parents=True, exist_ok=True)
    (detections_dir / "rec1").mkdir(exist_ok=True)
    (detections_dir / "rec1" / "chunk_a.json").write_text('{"chunk_id": "chunk_a", "status": "ok"}')
    result = runner.invoke(app, ["infer", "aggregate", str(detections_dir)])
    assert result.exit_code == 0
    assert "Wrote detection summary" in result.stdout
