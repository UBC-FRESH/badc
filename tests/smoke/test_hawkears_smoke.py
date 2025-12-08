"""End-to-end HawkEars smoke test gated behind an env flag."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

SMOKE_FLAG = "BADC_RUN_HAWKEARS_SMOKE"
MANIFEST = Path("data/datalad/bogus/manifests/XXXX-000_20251001_093000.csv")


def _first_manifest_row() -> tuple[str, str, Path] | None:
    if not MANIFEST.exists():
        return None
    lines = MANIFEST.read_text(encoding="utf-8").strip().splitlines()
    if len(lines) < 2:
        return None
    header = lines[0].split(",")
    row = lines[1].split(",")
    mapping = dict(zip(header, row, strict=True))
    recording_id = mapping["recording_id"]
    chunk_id = mapping["chunk_id"]
    source_path = Path(mapping["source_path"])
    if not source_path.exists():
        return None
    return recording_id, chunk_id, source_path


@pytest.mark.skipif(
    os.environ.get(SMOKE_FLAG) not in {"1", "true", "TRUE"},
    reason="HawkEars smoke test requires BADC_RUN_HAWKEARS_SMOKE=1",
)
def test_hawkears_infer_run_config(tmp_path: Path) -> None:
    """Run `badc infer run-config` against one bogus chunk and assert artifacts exist."""

    manifest_info = _first_manifest_row()
    if manifest_info is None:
        pytest.skip("Bogus manifest/chunks are missing locally; cannot run HawkEars smoke test.")
    recording_id, chunk_id, _ = manifest_info
    subset_manifest = tmp_path / "manifest.csv"
    # Write header + single row so the smoke test executes quickly.
    lines = MANIFEST.read_text(encoding="utf-8").strip().splitlines()
    subset_manifest.write_text("\n".join([lines[0], lines[1]]) + "\n", encoding="utf-8")

    output_dir = tmp_path / "infer_output"
    telemetry_log = tmp_path / "telemetry.jsonl"
    config = tmp_path / "hawkears-smoke.toml"
    config.write_text(
        "\n".join(
            [
                "[runner]",
                f'manifest = "{subset_manifest}"',
                "use_hawkears = true",
                "max_gpus = 1",
                "cpu_workers = 1",
                f'output_dir = "{output_dir}"',
                f'telemetry_log = "{telemetry_log}"',
                "",
                "[hawkears]",
                'extra_args = ["--min_score", "0.75"]',
            ]
        ),
        encoding="utf-8",
    )

    cmd = [
        sys.executable,
        "-m",
        "badc.cli.main",
        "infer",
        "run-config",
        str(config),
    ]
    subprocess.run(cmd, check=True, cwd=Path(__file__).resolve().parents[2])

    json_path = output_dir / recording_id / f"{chunk_id}.json"
    assert json_path.exists(), f"Expected smoke output {json_path}"
    assert telemetry_log.exists(), "Telemetry log should be written"
