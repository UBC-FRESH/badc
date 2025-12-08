from __future__ import annotations

import json
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
    audio = dataset / "audio" / "rec.wav"
    _write_wav(audio, duration_s=1.0)
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
        ],
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
    )
    assert result.exit_code == 0, result.stdout
    assert plan_csv.exists()
    assert plan_json.exists()
