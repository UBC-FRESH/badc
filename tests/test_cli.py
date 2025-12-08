from __future__ import annotations

import subprocess
import tomllib
from pathlib import Path

from typer.testing import CliRunner

import badc.cli.main as cli_main
from badc import data as data_utils
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


def test_infer_run_defaults_to_dataset_output(tmp_path) -> None:
    dataset = tmp_path / "dataset"
    (dataset / ".datalad").mkdir(parents=True)
    chunk_path = dataset / "chunk.wav"
    chunk_path.write_text("audio", encoding="utf-8")
    manifest = dataset / "manifest.csv"
    manifest.write_text(
        "recording_id,chunk_id,source_path,start_ms,end_ms,overlap_ms,sha256,notes\n"
        f"rec1,chunk_a,{chunk_path},0,1000,0,hash,\n",
        encoding="utf-8",
    )
    result = runner.invoke(app, ["infer", "run", str(manifest)])
    assert result.exit_code == 0, result.stdout
    expected = dataset / "artifacts" / "infer" / "rec1" / "chunk_a.json"
    assert expected.exists()


def test_infer_print_datalad_run(tmp_path) -> None:
    dataset = tmp_path / "dataset"
    (dataset / ".datalad").mkdir(parents=True)
    chunk_path = dataset / "chunk.wav"
    chunk_path.write_text("audio", encoding="utf-8")
    manifest = dataset / "manifest.csv"
    manifest.write_text(
        "recording_id,chunk_id,source_path,start_ms,end_ms,overlap_ms,sha256,notes\n"
        f"rec1,chunk_a,{chunk_path},0,1000,0,hash,\n",
        encoding="utf-8",
    )
    result = runner.invoke(app, ["infer", "run", str(manifest), "--print-datalad-run"])
    assert result.exit_code == 0
    assert "datalad run" in result.stdout
    assert "--telemetry-log" in result.stdout


def test_data_status_summary(tmp_path, monkeypatch) -> None:
    config_path = tmp_path / "data.toml"
    monkeypatch.setenv("BADC_DATA_CONFIG", str(config_path))
    dataset_dir = tmp_path / "datasets" / "bogus"
    (dataset_dir / ".git").mkdir(parents=True)
    data_utils.save_data_config(
        {
            "datasets": {
                "bogus": {
                    "path": str(dataset_dir),
                    "url": "https://example.com/bogus.git",
                    "method": "git",
                    "status": "connected",
                }
            }
        },
        config_path=config_path,
    )
    result = runner.invoke(app, ["data", "status"])
    assert result.exit_code == 0
    assert "bogus" in result.stdout
    assert "[present]" in result.stdout


def test_data_status_details_with_siblings(tmp_path, monkeypatch) -> None:
    config_path = tmp_path / "data.toml"
    monkeypatch.setenv("BADC_DATA_CONFIG", str(config_path))
    dataset_dir = tmp_path / "datasets" / "bogus"
    (dataset_dir / ".datalad").mkdir(parents=True)
    data_utils.save_data_config(
        {
            "datasets": {
                "bogus": {
                    "path": str(dataset_dir),
                    "url": "https://example.com/bogus.git",
                    "method": "datalad",
                    "status": "connected",
                }
            }
        },
        config_path=config_path,
    )

    sibling = data_utils.SiblingInfo(
        name="origin",
        url="https://example.com/bogus.git",
        push_url=None,
        here=True,
        description=None,
        status="present",
    )
    monkeypatch.setattr(
        cli_main.data_utils,
        "_siblings_via_datalad",
        lambda path: ([sibling], None),
    )

    result = runner.invoke(app, ["data", "status", "--details", "--show-siblings"])
    assert result.exit_code == 0
    assert "origin" in result.stdout
    assert "Siblings" in result.stdout


def test_gpus_reports_permission_error(monkeypatch) -> None:
    def fake_run(*args, **kwargs):
        raise subprocess.CalledProcessError(
            returncode=1,
            cmd=args[0],
            stderr="Failed to initialize NVML: Insufficient Permissions\n",
        )

    monkeypatch.setattr("badc.gpu.subprocess.run", fake_run)
    result = runner.invoke(app, ["gpus"])
    assert result.exit_code == 0
    assert "Insufficient Permissions" in result.stdout
    assert "No GPUs detected via nvidia-smi." in result.stdout
