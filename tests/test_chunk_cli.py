from __future__ import annotations

import json
import os
import wave
from pathlib import Path

from typer.testing import CliRunner

from badc.cli.main import app

runner = CliRunner()


def _write_wav(path: Path, duration_s: float = 2.0, sample_rate: int = 8000) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frames = int(sample_rate * duration_s)
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(b"\x00\x00" * frames)


def test_chunk_probe_estimation(tmp_path: Path) -> None:
    audio = tmp_path / "sample.wav"
    _write_wav(audio, duration_s=2.0)
    log_path = tmp_path / "probe.jsonl"
    result = runner.invoke(
        app,
        [
            "chunk",
            "probe",
            str(audio),
            "--initial-duration",
            "1",
            "--max-duration",
            "3",
            "--tolerance",
            "0.5",
            "--log",
            str(log_path),
        ],
    )
    assert result.exit_code == 0, result.stdout
    assert "Recommended chunk duration" in result.stdout
    assert log_path.exists()
    entries = [json.loads(line) for line in log_path.read_text().splitlines() if line.strip()]
    assert entries, "probe log should have entries"
    assert entries[-1]["duration_s"] <= 3


def test_chunk_split_placeholder(tmp_path: Path) -> None:
    audio = tmp_path / "sample.wav"
    _write_wav(audio, duration_s=2.0)
    result = runner.invoke(app, ["chunk", "split", str(audio), "--chunk-duration", "30"])
    assert result.exit_code == 0
    assert "placeholder chunks" in result.stdout


def test_chunk_orchestrate_lists_plan(tmp_path: Path) -> None:
    dataset = tmp_path / "dataset"
    audio = dataset / "audio" / "rec.wav"
    audio.parent.mkdir(parents=True, exist_ok=True)
    audio.write_bytes(b"\x00")
    result = runner.invoke(
        app,
        [
            "chunk",
            "orchestrate",
            str(dataset),
            "--pattern",
            "*.wav",
            "--chunk-duration",
            "45",
            "--overlap",
            "1.5",
            "--print-datalad-run",
        ],
    )
    assert result.exit_code == 0, result.stdout
    assert "Chunk plan" in result.stdout
    assert "rec.wav" in result.stdout
    assert "--chunk-duration 45.0" in result.stdout


def test_chunk_orchestrate_apply_runs_chunk(tmp_path: Path) -> None:
    dataset = tmp_path / "dataset"
    (dataset / ".datalad").mkdir(parents=True)
    audio = dataset / "audio" / "rec.wav"
    _write_wav(audio, duration_s=1.0)
    env = {**os.environ, "BADC_DISABLE_DATALAD": "1"}
    result = runner.invoke(
        app,
        [
            "chunk",
            "orchestrate",
            str(dataset),
            "--chunk-duration",
            "0.25",
            "--overlap",
            "0",
            "--apply",
            "--no-record-datalad",
        ],
        env=env,
    )
    assert result.exit_code == 0, result.stdout
    manifest = dataset / "manifests" / "rec.csv"
    chunks_dir = dataset / "artifacts" / "chunks" / "rec"
    assert manifest.exists()
    assert chunks_dir.exists()
    plan_csv = dataset / "plan.csv"
    plan_json = dataset / "plan.json"
    result = runner.invoke(
        app,
        [
            "chunk",
            "orchestrate",
            str(dataset),
            "--chunk-duration",
            "0.25",
            "--include-existing",
            "--plan-csv",
            str(plan_csv),
            "--plan-json",
            str(plan_json),
        ],
        env=env,
    )
    assert result.exit_code == 0, result.stdout
    assert plan_csv.exists()
    assert plan_json.exists()


def test_chunk_orchestrate_apply_warns_without_datalad(tmp_path: Path) -> None:
    dataset = tmp_path / "dataset_warn"
    (dataset / ".datalad").mkdir(parents=True)
    audio = dataset / "audio" / "rec.wav"
    _write_wav(audio, duration_s=0.5)
    env = {**os.environ, "BADC_DISABLE_DATALAD": "1"}
    result = runner.invoke(
        app,
        [
            "chunk",
            "orchestrate",
            str(dataset),
            "--chunk-duration",
            "0.25",
            "--apply",
        ],
        env=env,
    )
    assert result.exit_code == 0, result.stdout
    assert "Falling back to direct chunk runs" in result.stdout
    assert (dataset / "manifests" / "rec.csv").exists()


def test_chunk_orchestrate_workers_and_status_file(tmp_path: Path) -> None:
    dataset = tmp_path / "dataset_workers"
    for idx in range(2):
        audio = dataset / "audio" / f"rec{idx}.wav"
        _write_wav(audio, duration_s=0.5)
    env = {**os.environ, "BADC_DISABLE_DATALAD": "1"}
    result = runner.invoke(
        app,
        [
            "chunk",
            "orchestrate",
            str(dataset),
            "--chunk-duration",
            "0.25",
            "--apply",
            "--no-record-datalad",
            "--workers",
            "2",
        ],
        env=env,
    )
    assert result.exit_code == 0, result.stdout
    for idx in range(2):
        manifest = dataset / "manifests" / f"rec{idx}.csv"
        assert manifest.exists()
        status_path = dataset / "artifacts" / "chunks" / f"rec{idx}" / ".chunk_status.json"
        assert status_path.exists()
        status_data = json.loads(status_path.read_text())
        assert status_data["status"] == "completed"
        assert status_data["manifest_rows"] > 0
        assert "started_at" in status_data and "completed_at" in status_data


def test_chunk_orchestrate_resumes_failed_status(tmp_path: Path) -> None:
    dataset = tmp_path / "dataset_resume"
    audio = dataset / "audio" / "rec.wav"
    _write_wav(audio, duration_s=0.5)
    env = {**os.environ, "BADC_DISABLE_DATALAD": "1"}
    initial = runner.invoke(
        app,
        [
            "chunk",
            "orchestrate",
            str(dataset),
            "--chunk-duration",
            "0.25",
            "--apply",
            "--no-record-datalad",
        ],
        env=env,
    )
    assert initial.exit_code == 0, initial.stdout
    status_path = dataset / "artifacts" / "chunks" / "rec" / ".chunk_status.json"
    status_data = json.loads(status_path.read_text())
    status_data["status"] = "failed"
    status_path.write_text(json.dumps(status_data))
    rerun = runner.invoke(
        app,
        [
            "chunk",
            "orchestrate",
            str(dataset),
            "--chunk-duration",
            "0.25",
            "--apply",
            "--no-record-datalad",
        ],
        env=env,
    )
    assert rerun.exit_code == 0, rerun.stdout
    updated_status = json.loads(status_path.read_text())
    assert updated_status["status"] == "completed"
