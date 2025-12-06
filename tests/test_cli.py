from __future__ import annotations

from typer.testing import CliRunner

from badc.cli.main import app

runner = CliRunner()


def test_version_command() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "BADC version" in result.stdout


def test_data_connect_stub() -> None:
    result = runner.invoke(app, ["data", "connect", "bogus"])
    assert result.exit_code == 0
    assert "TODO" in result.stdout
