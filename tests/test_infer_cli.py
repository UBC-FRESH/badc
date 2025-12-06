from __future__ import annotations

from typer.testing import CliRunner

from badc.cli.main import app

runner = CliRunner()


def test_infer_run_placeholder() -> None:
    result = runner.invoke(app, ["infer", "run", "chunk_a", "chunk_b"])
    assert result.exit_code == 0
    assert "chunk_a_detected" in result.stdout


def test_infer_aggregate_placeholder() -> None:
    result = runner.invoke(
        app,
        [
            "infer",
            "aggregate",
            "chunk_a_detected",
            "chunk_a_detected",
            "chunk_b_detected",
        ],
    )
    assert result.exit_code == 0
    assert "chunk_a" in result.stdout
    assert "2 detections" in result.stdout
