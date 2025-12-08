from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from badc.aggregate import DetectionRecord, write_parquet
from badc.cli.main import app
from badc.telemetry import TelemetryRecord, log_telemetry, now_iso

runner = CliRunner()


def test_infer_run_placeholder(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.csv"
    manifest.write_text(
        "recording_id,chunk_id,source_path,start_ms,end_ms,overlap_ms,sha256,notes\n"
        "rec1,chunk_a,data/datalad/bogus/audio/foo.wav,0,1000,0,hash,\n"
    )
    result = runner.invoke(app, ["infer", "run", str(manifest), "--runner-cmd", "echo stub"])
    assert result.exit_code == 0
    assert "Processed 1 jobs" in result.stdout
    assert "Telemetry log" in result.stdout


def test_infer_aggregate_placeholder() -> None:
    detections_dir = Path("artifacts/infer_test")
    detections_dir.mkdir(parents=True, exist_ok=True)
    (detections_dir / "rec1").mkdir(exist_ok=True)
    (detections_dir / "rec1" / "chunk_a.json").write_text(
        '{"chunk_id": "chunk_a", "status": "ok", "detections": '
        '[{"timestamp_ms": 123, "label": "grouse", "confidence": 0.9}]}'
    )
    result = runner.invoke(app, ["infer", "aggregate", str(detections_dir)])
    assert result.exit_code == 0
    assert "Wrote detection summary" in result.stdout


def test_infer_aggregate_with_manifest(tmp_path: Path) -> None:
    detections_dir = tmp_path / "artifacts" / "infer"
    chunk_dir = detections_dir / "rec_stub"
    chunk_dir.mkdir(parents=True)
    (chunk_dir / "chunk_a.json").write_text(
        '{"chunk_id": "chunk_a", "status": "ok", "detections": [{"timestamp_ms": 0, "label": "grouse"}]}',
        encoding="utf-8",
    )
    manifest = tmp_path / "manifest.csv"
    manifest.write_text(
        "recording_id,chunk_id,source_path,start_ms,end_ms,overlap_ms,sha256,notes\n"
        f"rec_manifest,chunk_a,{tmp_path / 'chunks' / 'chunk_a.wav'},0,1000,0,hash123,\n",
        encoding="utf-8",
    )
    output = tmp_path / "summary.csv"
    result = runner.invoke(
        app,
        [
            "infer",
            "aggregate",
            str(detections_dir),
            "--manifest",
            str(manifest),
            "--output",
            str(output),
        ],
    )
    assert result.exit_code == 0, result.stdout
    contents = output.read_text(encoding="utf-8")
    assert "rec_manifest" in contents


def test_infer_monitor_outputs_tables(tmp_path: Path) -> None:
    log_path = tmp_path / "telemetry.jsonl"
    record = TelemetryRecord(
        chunk_id="chunk_a",
        gpu_index=0,
        gpu_name="GPU 0",
        status="success",
        timestamp=now_iso(),
        finished_at=now_iso(),
        runtime_s=1.2,
        details={
            "gpu_metrics": {
                "after": {"utilization": 50, "memory_used_mb": 1024, "memory_total_mb": 8192}
            }
        },
    )
    log_telemetry(record, log_path)
    result = runner.invoke(app, ["infer", "monitor", "--log", str(log_path)])
    assert result.exit_code == 0
    assert "GPU Summary" in result.stdout


def test_report_summary_cli(tmp_path: Path) -> None:
    pytest.importorskip("duckdb")
    parquet_path = tmp_path / "detections.parquet"
    records = [
        DetectionRecord(
            recording_id="rec1",
            chunk_id="chunk_a",
            chunk_start_ms=0,
            chunk_end_ms=1000,
            timestamp_ms=100,
            absolute_time_ms=100,
            label="grouse",
            confidence=0.9,
            status="ok",
            runner="hawkears",
            chunk_sha256="abc123",
            source_path=tmp_path / "chunk_a.json",
            dataset_root=tmp_path,
        )
    ]
    write_parquet(records, parquet_path)
    result = runner.invoke(
        app,
        [
            "report",
            "summary",
            "--parquet",
            str(parquet_path),
            "--group-by",
            "label",
            "--limit",
            "5",
        ],
    )
    assert result.exit_code == 0, result.stdout
    assert "Detection summary" in result.stdout
