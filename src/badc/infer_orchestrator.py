"""Helpers for planning dataset-wide inference runs."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence


@dataclass(frozen=True, slots=True)
class InferPlan:
    """Plan describing how to run inference for a manifest."""

    manifest_path: Path
    output_dir: Path
    telemetry_log: Path
    use_hawkears: bool = True
    hawkears_args: Sequence[str] = ()
    max_gpus: int | None = None

    @property
    def recording_id(self) -> str:
        return self.manifest_path.stem

    def to_dict(self) -> dict[str, str | int | bool | Sequence[str] | None]:
        return {
            "recording_id": self.recording_id,
            "manifest_path": str(self.manifest_path),
            "output_dir": str(self.output_dir),
            "telemetry_log": str(self.telemetry_log),
            "use_hawkears": self.use_hawkears,
            "hawkears_args": list(self.hawkears_args),
            "max_gpus": self.max_gpus,
        }


def _resolve(base: Path, value: Path) -> Path:
    return value if value.is_absolute() else (base / value)


def build_infer_plan(
    dataset_root: Path,
    *,
    manifest_paths: Iterable[Path] | None = None,
    manifest_dir: Path = Path("manifests"),
    pattern: str = "*.csv",
    output_dir: Path = Path("artifacts/infer"),
    telemetry_dir: Path = Path("artifacts/telemetry"),
    include_existing: bool = False,
    use_hawkears: bool = True,
    hawkears_args: Sequence[str] | None = None,
    max_gpus: int | None = None,
    limit: int | None = None,
) -> list[InferPlan]:
    """Return inference plans for manifests under ``dataset_root``."""

    dataset_root = dataset_root.expanduser().resolve()
    manifest_root = _resolve(dataset_root, manifest_dir)
    output_root = _resolve(dataset_root, output_dir)
    telemetry_root = _resolve(dataset_root, telemetry_dir)
    hawkears_args = tuple(hawkears_args or [])

    if manifest_paths is None:
        candidates = sorted(manifest_root.rglob(pattern))
    else:
        candidates = [Path(p).resolve() for p in manifest_paths]

    plans: list[InferPlan] = []
    for manifest_path in candidates:
        if not manifest_path.exists():
            continue
        recording_id = manifest_path.stem
        recording_output = output_root / recording_id
        if not include_existing and recording_output.exists():
            continue
        telemetry_log = telemetry_root / "infer" / f"{recording_id}.jsonl"
        plans.append(
            InferPlan(
                manifest_path=manifest_path,
                output_dir=recording_output,
                telemetry_log=telemetry_log,
                use_hawkears=use_hawkears,
                hawkears_args=hawkears_args,
                max_gpus=max_gpus,
            )
        )
        if limit and len(plans) >= limit:
            break
    return plans


def render_datalad_run(plan: InferPlan, dataset_root: Path) -> str:
    """Return a ready-to-run ``datalad run`` command for the provided plan."""

    dataset_root = dataset_root.expanduser().resolve()
    manifest_abs = plan.manifest_path.resolve()
    output_abs = plan.output_dir.resolve()
    telemetry_abs = plan.telemetry_log.resolve()
    try:
        manifest_rel = manifest_abs.relative_to(dataset_root)
        output_rel = output_abs.relative_to(dataset_root)
        telemetry_rel = telemetry_abs.relative_to(dataset_root)
    except ValueError as exc:  # pragma: no cover - defensive
        raise ValueError("Plan paths must live inside the dataset root.") from exc

    cmd = [
        "badc",
        "infer",
        "run",
        str(manifest_rel),
        "--output-dir",
        str(output_rel),
        "--telemetry-log",
        str(telemetry_rel),
    ]
    if plan.max_gpus is not None:
        cmd += ["--max-gpus", str(plan.max_gpus)]
    if plan.use_hawkears:
        cmd.append("--use-hawkears")
    for arg in plan.hawkears_args:
        cmd += ["--hawkears-arg", arg]

    return (
        f'datalad run -m "Infer {plan.recording_id}" '
        f"--input {manifest_rel} "
        f"--output {output_rel} "
        f"-- badc infer run {manifest_rel} " + " ".join(cmd[4:])
    )


def load_manifest_paths_from_plan(plan_path: Path) -> list[Path]:
    """Load manifest paths from a chunk/infer plan file (CSV or JSON)."""

    plan_path = plan_path.expanduser()
    if not plan_path.exists():
        raise FileNotFoundError(plan_path)
    manifest_paths: list[Path] = []
    if plan_path.suffix.lower() == ".json":
        records = json.loads(plan_path.read_text())
        for record in records:
            manifest = record.get("manifest_path") or record.get("manifest")
            if manifest:
                manifest_paths.append(Path(manifest))
    else:
        with plan_path.open() as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                manifest = row.get("manifest_path") or row.get("manifest")
                if manifest:
                    manifest_paths.append(Path(manifest))
    return manifest_paths
