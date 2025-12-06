from __future__ import annotations

import subprocess
import tomllib
from pathlib import Path

from typer.testing import CliRunner

from badc.cli.main import app

runner = CliRunner()


def test_version_command() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "BADC version" in result.stdout


def _init_git_repo(root: Path) -> Path:
    repo = root / "source-repo"
    repo.mkdir()
    subprocess.run(["git", "init", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "ci@example.com"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "CI"], check=True)
    readme = repo / "README.md"
    readme.write_text("# demo\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "README.md"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-m", "init"], check=True)
    return repo


def test_data_connect_and_disconnect(tmp_path, monkeypatch) -> None:
    config_path = tmp_path / "config" / "data.toml"
    monkeypatch.setenv("BADC_DATA_CONFIG", str(config_path))

    source_repo = _init_git_repo(tmp_path)
    datasets_dir = tmp_path / "datasets"

    connect_result = runner.invoke(
        app,
        [
            "data",
            "connect",
            "bogus",
            "--path",
            str(datasets_dir),
            "--url",
            str(source_repo),
            "--method",
            "git",
        ],
    )
    assert connect_result.exit_code == 0, connect_result.stdout
    target_dir = datasets_dir / "bogus"
    assert target_dir.exists()

    config = tomllib.loads(config_path.read_text(encoding="utf-8"))
    entry = config["datasets"]["bogus"]
    assert entry["status"] == "connected"

    status_result = runner.invoke(app, ["data", "status"])
    assert status_result.exit_code == 0
    assert "bogus" in status_result.stdout

    disconnect_result = runner.invoke(
        app,
        [
            "data",
            "disconnect",
            "bogus",
            "--drop-content",
            "--path",
            str(datasets_dir),
        ],
    )
    assert disconnect_result.exit_code == 0
    assert not target_dir.exists()
    new_config = tomllib.loads(config_path.read_text(encoding="utf-8"))
    assert new_config["datasets"]["bogus"]["status"] == "disconnected"


def test_infer_run_stub_cpu_workers(tmp_path) -> None:
    chunk_path = tmp_path / "chunk.wav"
    chunk_path.write_text("stub audio", encoding="utf-8")
    manifest = tmp_path / "manifest.csv"
    manifest.write_text(
        "recording_id,chunk_id,source_path,start_ms,end_ms,overlap_ms,sha256,notes\n"
        f"rec1,chunk_a,{chunk_path},0,1000,0,hash,\n"
        f"rec1,chunk_b,{chunk_path},0,1000,0,hash,\n"
        f"rec1,chunk_c,{chunk_path},0,1000,0,hash,\n",
        encoding="utf-8",
    )
    result = runner.invoke(
        app,
        [
            "infer",
            "run",
            str(manifest),
            "--cpu-workers",
            "2",
        ],
    )
    assert result.exit_code == 0, result.stdout
    out_dir = Path("artifacts/infer/rec1")
    assert (out_dir / "chunk_a.json").exists()
    assert (out_dir / "chunk_b.json").exists()
    assert (out_dir / "chunk_c.json").exists()
