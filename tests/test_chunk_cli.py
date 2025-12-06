from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from badc.cli.main import app

runner = CliRunner()


def test_chunk_probe_placeholder(tmp_path: Path) -> None:
    audio = tmp_path / "sample.wav"
    audio.write_bytes(b"fake data")
    result = runner.invoke(app, ["chunk", "probe", str(audio), "--initial-duration", "90"])
    assert result.exit_code == 0
    assert "90.00" in result.stdout


def test_chunk_split_placeholder(tmp_path: Path) -> None:
    audio = tmp_path / "sample.wav"
    audio.write_bytes(b"fake data")
    result = runner.invoke(app, ["chunk", "split", str(audio), "--chunk-duration", "30"])
    assert result.exit_code == 0
    assert "placeholder chunks" in result.stdout
