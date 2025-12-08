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


def test_infer_orchestrate_plan(tmp_path: Path) -> None:
    dataset = tmp_path / "dataset"
    manifest_dir = dataset / "manifests"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    manifest = manifest_dir / "rec.csv"
    manifest.write_text(
        "recording_id,chunk_id,source_path,start_ms,end_ms,overlap_ms,sha256,notes\n"
        "rec,chunk_a,data/foo.wav,0,1000,0,hash,\n",
        encoding="utf-8",
    )
    result = runner.invoke(
        app,
        [
            "infer",
            "orchestrate",
            str(dataset),
            "--manifest-dir",
            str(manifest_dir),
            "--plan-csv",
            str(dataset / "plan.csv"),
            "--plan-json",
            str(dataset / "plan.json"),
            "--limit",
            "1",
            "--print-datalad-run",
        ],
    )
    assert result.exit_code == 0, result.stdout
    assert "Inference plan" in result.stdout
    assert (dataset / "plan.csv").exists()
    assert (dataset / "plan.json").exists()


def test_infer_run_config(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.csv"
    manifest.write_text(
        "recording_id,chunk_id,source_path,start_ms,end_ms,overlap_ms,sha256,notes\n"
        f"rec1,chunk_a,{tmp_path / 'chunk.wav'},0,1000,0,hash,\n",
        encoding="utf-8",
    )
    config = tmp_path / "hawkears-local.toml"
    output_dir = tmp_path / "artifacts" / "infer"
    telemetry_log = tmp_path / "telemetry.jsonl"
    config.write_text(
        "\n".join(
            [
                "[runner]",
                f'manifest = "{manifest}"',
                'runner_cmd = "echo stub"',
                f'output_dir = "{output_dir}"',
                f'telemetry_log = "{telemetry_log}"',
                "use_hawkears = false",
                "cpu_workers = 1",
                "",
                "[hawkears]",
                'extra_args = ["--min_score", "0.5"]',
            ]
        ),
        encoding="utf-8",
    )
    result = runner.invoke(app, ["infer", "run-config", str(config)])
    assert result.exit_code == 0, result.stdout
    assert "Processed 1 jobs" in result.stdout


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
    assert "GPU Utilization" in result.stdout
    assert "Last 15 Events" in result.stdout


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


def test_report_quicklook_cli(tmp_path: Path) -> None:
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
            label_name="Grouse",
            confidence=0.9,
            status="ok",
            runner="hawkears",
            chunk_sha256="abc123",
            source_path=tmp_path / "chunk_a.json",
            dataset_root=tmp_path,
        ),
        DetectionRecord(
            recording_id="rec2",
            chunk_id="chunk_b",
            chunk_start_ms=1000,
            chunk_end_ms=2000,
            timestamp_ms=200,
            absolute_time_ms=1200,
            label="grouse",
            label_name="Grouse",
            confidence=0.95,
            status="ok",
            runner="hawkears",
            chunk_sha256="def456",
            source_path=tmp_path / "chunk_b.json",
            dataset_root=tmp_path,
        ),
    ]
    write_parquet(records, parquet_path)
    output_dir = tmp_path / "quicklook"
    result = runner.invoke(
        app,
        [
            "report",
            "quicklook",
            "--parquet",
            str(parquet_path),
            "--top-labels",
            "5",
            "--top-recordings",
            "2",
            "--output-dir",
            str(output_dir),
        ],
    )
    assert result.exit_code == 0, result.stdout
    assert "Top 5 labels" in result.stdout
    assert "Chunk timeline" in result.stdout
    assert (output_dir / "labels.csv").exists()
    assert (output_dir / "recordings.csv").exists()
    assert (output_dir / "chunks.csv").exists()
