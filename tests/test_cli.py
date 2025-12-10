from __future__ import annotations

import subprocess
import tomllib
from pathlib import Path

from typer.testing import CliRunner

import badc.cli.main as cli_main
from badc import data as data_utils
from badc.cli.main import app
from badc.hawkears_runner import JobResult
from badc.infer_scheduler import InferenceJob
from badc.telemetry import TelemetryRecord

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
    assert "Worker summary" in result.stdout
    assert "Retries" in result.stdout
    assert "cpu-0" in result.stdout
    assert "cpu-1" in result.stdout


def test_run_scheduler_tracks_retries(tmp_path, monkeypatch) -> None:
    chunk_path = tmp_path / "chunk.wav"
    chunk_path.write_text("stub audio", encoding="utf-8")
    job = InferenceJob(
        chunk_id="chunk_a",
        chunk_path=chunk_path,
        recording_id="rec1",
    )
    output_dir = tmp_path / "outputs"
    telemetry_log = tmp_path / "telemetry.jsonl"

    def fake_run_job(**kwargs):
        rec_dir = output_dir / job.recording_id
        rec_dir.mkdir(parents=True, exist_ok=True)
        path = rec_dir / f"{job.chunk_id}.json"
        path.write_text("{}", encoding="utf-8")
        return JobResult(output_path=path, attempts=3, retries=2)

    monkeypatch.setattr(cli_main, "run_job", fake_run_job)
    stats = cli_main._run_scheduler(
        job_contexts=[(job, output_dir, None)],
        worker_pool=[(None, "cpu-0")],
        runner_cmd=None,
        max_retries=2,
        use_hawkears=False,
        hawkears_args=[],
        telemetry_path=telemetry_log,
    )
    assert stats["cpu-0"]["success"] == 1
    assert stats["cpu-0"]["retries"] == 2


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


def test_summarize_gpu_stats_tracks_utilization() -> None:
    records: list[TelemetryRecord] = []
    for idx in range(30):
        records.append(
            TelemetryRecord(
                chunk_id=f"chunk_gpu_{idx}",
                gpu_index=0,
                gpu_name="Quadro RTX 4000",
                status="success" if idx % 2 == 0 else "failure",
                timestamp=f"2025-12-08T20:{13 + idx:02d}:00Z",
                finished_at=None,
                runtime_s=10.0 + idx,
                details={
                    "gpu_metrics": {
                        "after": {
                            "utilization": 10 + idx,
                            "memory_used_mb": 5400 + idx,
                            "memory_total_mb": 8192,
                        }
                    }
                },
            )
        )
    records.append(
        TelemetryRecord(
            chunk_id="chunk_cpu",
            gpu_index=None,
            gpu_name=None,
            status="success",
            timestamp="2025-12-08T21:00:00Z",
            finished_at="2025-12-08T21:00:01Z",
            runtime_s=3.0,
            details={},
        )
    )
    summary = cli_main._summarize_gpu_stats(records)
    assert "GPU 0" in summary
    gpu0 = summary["GPU 0"]
    assert gpu0["events"] == 30
    assert gpu0["success"] == 15
    assert gpu0["failures"] == 15
    assert gpu0["avg_runtime"] > 10.0
    assert gpu0["util_stats"]["min"] == 10.0
    assert gpu0["util_stats"]["max"] == 39.0
    assert gpu0["max_memory"] == 5429.0
    assert gpu0["memory_total"] == 8192
    assert gpu0["last_chunk"] == "chunk_gpu_29"
    assert gpu0["util_history"]
    assert len(gpu0["util_history"]) == 24
    assert len(gpu0["memory_history"]) == 24

    cpu = summary["CPU"]
    assert cpu["events"] == 1
    assert cpu["success"] == 1
    assert cpu["avg_runtime"] == 3.0


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


def test_sparkline_handles_constant_values() -> None:
    spark = cli_main._sparkline([5.0, 5.0, 5.0], width=3)
    assert len(spark) == 3
    assert spark.strip()
    assert cli_main._sparkline([], width=3) == "-"
