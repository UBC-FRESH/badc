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
