from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from typer.testing import CliRunner

from badc.aggregate import DetectionRecord, write_parquet
from badc.cli.main import app
from badc.telemetry import TelemetryRecord, log_telemetry, now_iso

runner = CliRunner()


def _write_chunk(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\x00\x00")


def test_infer_run_placeholder(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.csv"
    chunk_path = tmp_path / "chunk.wav"
    _write_chunk(chunk_path)
    telemetry_log = tmp_path / "telemetry.jsonl"
    output_dir = tmp_path / "outputs"
    manifest.write_text(
        "recording_id,chunk_id,source_path,start_ms,end_ms,overlap_ms,sha256,notes\n"
        f"rec1,chunk_a,{chunk_path},0,1000,0,hash,\n"
    )
    result = runner.invoke(
        app,
        [
            "infer",
            "run",
            str(manifest),
            "--runner-cmd",
            "echo stub",
            "--output-dir",
            str(output_dir),
            "--telemetry-log",
            str(telemetry_log),
        ],
    )
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


def test_infer_orchestrate_cpu_workers(tmp_path: Path) -> None:
    dataset = tmp_path / "dataset_cpu"
    manifest_dir = dataset / "manifests"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    manifest = manifest_dir / "rec.csv"
    manifest.write_text(
        "recording_id,chunk_id,source_path,start_ms,end_ms,overlap_ms,sha256,notes\n"
        "rec,chunk_a,data/foo.wav,0,1000,0,hash,\n",
        encoding="utf-8",
    )
    plan_json = dataset / "plan.json"
    result = runner.invoke(
        app,
        [
            "infer",
            "orchestrate",
            str(dataset),
            "--manifest-dir",
            str(manifest_dir),
            "--plan-json",
            str(plan_json),
            "--cpu-workers",
            "3",
            "--print-datalad-run",
        ],
    )
    assert result.exit_code == 0, result.stdout
    plan = json.loads(plan_json.read_text(encoding="utf-8"))
    assert plan[0]["cpu_workers"] == 3
    assert "--cpu-workers 3" in result.stdout


def test_infer_orchestrate_apply_runs_infer(tmp_path: Path) -> None:
    dataset = tmp_path / "dataset_apply"
    (dataset / ".datalad").mkdir(parents=True)
    manifest_dir = dataset / "manifests"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    chunk_path = dataset / "chunks" / "rec" / "chunk_a.wav"
    _write_chunk(chunk_path)
    manifest = manifest_dir / "rec.csv"
    manifest.write_text(
        "recording_id,chunk_id,source_path,start_ms,end_ms,overlap_ms,sha256,notes\n"
        f"rec,chunk_a,{chunk_path},0,1000,0,hash,\n",
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
            "--stub-runner",
            "--apply",
            "--no-record-datalad",
        ],
    )
    assert result.exit_code == 0, result.stdout
    output_dir = dataset / "artifacts" / "infer" / "rec"
    telemetry_log = dataset / "artifacts" / "telemetry" / "infer" / "rec.jsonl"
    assert output_dir.exists()
    assert any(output_dir.glob("*.json"))
    assert telemetry_log.exists()


def test_infer_orchestrate_apply_warns_without_datalad(tmp_path: Path) -> None:
    dataset = tmp_path / "dataset_warn"
    (dataset / ".datalad").mkdir(parents=True)
    manifest_dir = dataset / "manifests"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    chunk_path = dataset / "chunks" / "rec" / "chunk_a.wav"
    _write_chunk(chunk_path)
    manifest = manifest_dir / "rec.csv"
    manifest.write_text(
        "recording_id,chunk_id,source_path,start_ms,end_ms,overlap_ms,sha256,notes\n"
        f"rec,chunk_a,{chunk_path},0,1000,0,hash,\n",
        encoding="utf-8",
    )
    env = {**os.environ, "BADC_DISABLE_DATALAD": "1"}
    result = runner.invoke(
        app,
        [
            "infer",
            "orchestrate",
            str(dataset),
            "--manifest-dir",
            str(manifest_dir),
            "--stub-runner",
            "--apply",
        ],
        env=env,
    )
    assert result.exit_code == 0, result.stdout
    assert "Falling back to direct inference runs" in result.stdout


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
            "attempt": 2,
            "gpu_metrics": {
                "after": {"utilization": 50, "memory_used_mb": 1024, "memory_total_mb": 8192}
            },
        },
    )
    log_telemetry(record, log_path)
    result = runner.invoke(app, ["infer", "monitor", "--log", str(log_path)])
    assert result.exit_code == 0
    assert "GPU Utilization" in result.stdout
    assert "Last 15 Events" in result.stdout
    assert "Attempt" in result.stdout


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


def test_infer_orchestrate_sockeye_script(tmp_path: Path) -> None:
    dataset = tmp_path / "dataset_sockeye"
    (dataset / ".datalad").mkdir(parents=True)
    manifest_dir = dataset / "manifests"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    chunk_path = dataset / "chunks" / "rec" / "chunk_a.wav"
    chunk_path.parent.mkdir(parents=True, exist_ok=True)
    chunk_path.write_text("audio", encoding="utf-8")
    manifest = manifest_dir / "rec.csv"
    manifest.write_text(
        "recording_id,chunk_id,source_path,start_ms,end_ms,overlap_ms,sha256,notes\n"
        f"rec,chunk_a,{chunk_path},0,1000,0,hash,\n",
        encoding="utf-8",
    )
    script_path = tmp_path / "sockeye.sh"
    result = runner.invoke(
        app,
        [
            "infer",
            "orchestrate",
            str(dataset),
            "--manifest-dir",
            str(manifest_dir),
            "--sockeye-script",
            str(script_path),
            "--sockeye-account",
            "def-sockeye",
        ],
    )
    assert result.exit_code == 0, result.stdout
    text = script_path.read_text(encoding="utf-8")
    assert "#SBATCH --array=1-1" in text
    assert "badc infer run" in text


def test_infer_orchestrate_sockeye_script_resume(tmp_path: Path) -> None:
    dataset = tmp_path / "dataset_sockeye_resume"
    (dataset / ".datalad").mkdir(parents=True)
    manifest_dir = dataset / "manifests"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    chunk_path = dataset / "chunks" / "rec" / "chunk_a.wav"
    chunk_path.parent.mkdir(parents=True, exist_ok=True)
    chunk_path.write_text("audio", encoding="utf-8")
    manifest = manifest_dir / "rec.csv"
    manifest.write_text(
        "recording_id,chunk_id,source_path,start_ms,end_ms,overlap_ms,sha256,notes\n"
        f"rec,chunk_a,{chunk_path},0,1000,0,hash,\n",
        encoding="utf-8",
    )
    script_path = tmp_path / "sockeye_resume.sh"
    result = runner.invoke(
        app,
        [
            "infer",
            "orchestrate",
            str(dataset),
            "--manifest-dir",
            str(manifest_dir),
            "--sockeye-script",
            str(script_path),
            "--sockeye-resume-completed",
        ],
    )
    assert result.exit_code == 0, result.stdout
    text = script_path.read_text(encoding="utf-8")
    assert "RESUMES=(" in text
    assert 'CMD+=("--resume-summary"' in text


def test_infer_orchestrate_sockeye_script_bundle(tmp_path: Path) -> None:
    dataset = tmp_path / "dataset_sockeye_bundle"
    (dataset / ".datalad").mkdir(parents=True)
    manifest_dir = dataset / "manifests"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    chunk_path = dataset / "chunks" / "rec" / "chunk_a.wav"
    chunk_path.parent.mkdir(parents=True, exist_ok=True)
    chunk_path.write_text("audio", encoding="utf-8")
    manifest = manifest_dir / "rec.csv"
    manifest.write_text(
        "recording_id,chunk_id,source_path,start_ms,end_ms,overlap_ms,sha256,notes\n"
        f"rec,chunk_a,{chunk_path},0,1000,0,hash,\n",
        encoding="utf-8",
    )
    script_path = tmp_path / "sockeye_bundle.sh"
    result = runner.invoke(
        app,
        [
            "infer",
            "orchestrate",
            str(dataset),
            "--manifest-dir",
            str(manifest_dir),
            "--include-existing",
            "--sockeye-script",
            str(script_path),
            "--sockeye-bundle",
            "--sockeye-bundle-aggregate-dir",
            "aggregates",
            "--sockeye-bundle-bucket-minutes",
            "15",
        ],
    )
    assert result.exit_code == 0, result.stdout
    text = script_path.read_text(encoding="utf-8")
    assert "badc infer aggregate" in text
    assert "badc report bundle" in text
    assert "--bucket-minutes 15" in text
