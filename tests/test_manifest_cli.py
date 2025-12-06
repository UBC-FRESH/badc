from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from badc.cli.main import app

TEST_AUDIO = Path(__file__).parent / "data" / "minimal.wav"

runner = CliRunner()


def test_chunk_manifest_creates_file(tmp_path: Path) -> None:
    output = tmp_path / "manifest.csv"
    result = runner.invoke(
        app,
        [
            "chunk",
            "manifest",
            str(TEST_AUDIO),
            "--chunk-duration",
            "30",
            "--output",
            str(output),
        ],
    )
    assert result.exit_code == 0
    assert output.exists()
    contents = output.read_text().splitlines()
    assert contents[0].startswith("recording_id")
