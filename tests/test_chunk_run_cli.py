from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from badc.cli.main import app

runner = CliRunner()


def test_chunk_run_creates_files(tmp_path: Path) -> None:
    audio = tmp_path / "test.wav"
    audio.write_bytes(Path("tests/data/minimal.wav").read_bytes())
    output_dir = tmp_path / "chunks"
    manifest = tmp_path / "manifest.csv"
    result = runner.invoke(
        app,
        [
            "chunk",
            "run",
            str(audio),
            "--chunk-duration",
            "0.5",
            "--overlap",
            "0.1",
            "--output-dir",
            str(output_dir),
            "--manifest",
            str(manifest),
        ],
    )
    assert result.exit_code == 0
    assert output_dir.exists()
    assert any(output_dir.iterdir())
    assert manifest.exists()
    lines = manifest.read_text().splitlines()
    assert len(lines) > 1


def test_chunk_run_defaults_inside_dataset(tmp_path: Path) -> None:
    dataset = tmp_path / "dataset"
    (dataset / ".datalad").mkdir(parents=True)
    audio_dir = dataset / "audio"
    audio_dir.mkdir()
    audio = audio_dir / "rec.wav"
    audio.write_bytes(Path("tests/data/minimal.wav").read_bytes())
    result = runner.invoke(
        app,
        [
            "chunk",
            "run",
            str(audio),
            "--chunk-duration",
            "0.5",
        ],
    )
    assert result.exit_code == 0, result.stdout
    chunk_dir = dataset / "artifacts" / "chunks" / "rec"
    assert chunk_dir.exists()
    assert any(chunk_dir.glob("*.wav"))
    manifest_path = dataset / "manifests" / "rec.csv"
    assert manifest_path.exists()
