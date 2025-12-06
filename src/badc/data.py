"""Helpers for tracking DataLad datasets and recording connection status."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tomllib
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

BADC_DATA_CONFIG = "BADC_DATA_CONFIG"


@dataclass(frozen=True)
class DatasetSpec:
    """Definition for a known dataset target."""

    name: str
    url: str
    description: str = ""


DEFAULT_DATASETS: dict[str, DatasetSpec] = {
    "bogus": DatasetSpec(
        name="bogus",
        url="https://github.com/UBC-FRESH/badc-bogus-data.git",
        description="Lightweight public dataset for smoke-testing chunk/infer flows.",
    ),
}


def get_data_config_path() -> Path:
    env_path = os.environ.get(BADC_DATA_CONFIG)
    if env_path:
        return Path(env_path).expanduser()
    return Path.home() / ".config" / "badc" / "data.toml"


def load_data_config(config_path: Path | None = None) -> dict[str, Any]:
    path = config_path or get_data_config_path()
    if not path.exists():
        return {"datasets": {}}
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    data.setdefault("datasets", {})
    return data


def save_data_config(config: dict[str, Any], config_path: Path | None = None) -> None:
    path = config_path or get_data_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    datasets: Dict[str, Dict[str, Any]] = config.get("datasets", {})
    for name in sorted(datasets):
        lines.append(f"[datasets.{name}]")
        entry = datasets[name]
        for key, value in entry.items():
            if isinstance(value, Path):
                serialized = json.dumps(str(value))
            else:
                serialized = json.dumps(value)
            lines.append(f"{key} = {serialized}")
        lines.append("")
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def get_dataset_spec(name: str) -> DatasetSpec:
    if name not in DEFAULT_DATASETS:
        raise KeyError(name)
    return DEFAULT_DATASETS[name]


def available_method(preferred: str | None = None) -> str:
    if preferred:
        return preferred.lower()
    if shutil.which("datalad"):
        return "datalad"
    return "git"


def _run(cmd: list[str], cwd: Path | None = None) -> None:
    subprocess.run(cmd, cwd=cwd, check=True)


def connect_dataset(
    spec: DatasetSpec,
    target_dir: Path,
    *,
    method: str | None = None,
    pull_existing: bool = True,
    dry_run: bool = False,
    config_path: Path | None = None,
) -> str:
    target_dir = target_dir.expanduser()
    target_dir.parent.mkdir(parents=True, exist_ok=True)

    method_name = available_method(method)
    status = ""

    if target_dir.exists():
        if pull_existing:
            status = "updated"
            if not dry_run:
                _update_dataset(target_dir, method_name)
        else:
            status = "exists"
    else:
        status = "cloned"
        if not dry_run:
            _clone_dataset(spec.url, target_dir, method_name)

    if not dry_run:
        _record_dataset_entry(
            spec,
            target_dir,
            method_name,
            status="connected",
            config_path=config_path,
        )
    return status


def disconnect_dataset(
    name: str,
    dataset_path: Path,
    *,
    drop_content: bool,
    dry_run: bool = False,
    config_path: Path | None = None,
) -> str:
    dataset_path = dataset_path.expanduser()
    action = "detached"
    if drop_content and dataset_path.exists():
        action = "removed"
        if not dry_run:
            shutil.rmtree(dataset_path)

    if not dry_run:
        _record_status_only(
            name,
            {
                "status": "disconnected",
                "last_disconnected": datetime.now(timezone.utc).isoformat(),
                "path": str(dataset_path),
            },
            config_path=config_path,
        )
    return action


def _record_dataset_entry(
    spec: DatasetSpec,
    path: Path,
    method: str,
    *,
    status: str,
    config_path: Path | None = None,
) -> None:
    config = load_data_config(config_path)
    dataset = {
        "path": str(path.resolve()),
        "url": spec.url,
        "method": method,
        "status": status,
        "last_connected": datetime.now(timezone.utc).isoformat(),
    }
    config.setdefault("datasets", {})[spec.name] = dataset
    save_data_config(config, config_path)


def _record_status_only(
    name: str,
    updates: Dict[str, Any],
    config_path: Path | None = None,
) -> None:
    config = load_data_config(config_path)
    entry = config.setdefault("datasets", {}).get(name, {})
    entry.update(updates)
    config["datasets"][name] = entry
    save_data_config(config, config_path)


def list_tracked_datasets(config_path: Path | None = None) -> dict[str, dict[str, Any]]:
    config = load_data_config(config_path)
    return config.get("datasets", {})


def resolve_dataset_path(
    name: str,
    base_path: Path,
    config_path: Path | None = None,
) -> Path:
    datasets = list_tracked_datasets(config_path)
    entry = datasets.get(name)
    if entry and entry.get("path"):
        return Path(entry["path"])
    return base_path.expanduser() / name


def override_spec_url(spec: DatasetSpec, url: str | None) -> DatasetSpec:
    if not url:
        return spec
    return replace(spec, url=url)


def _clone_dataset(url: str, target: Path, method: str) -> None:
    if method == "datalad":
        cmd = ["datalad", "clone", url, str(target)]
    elif method == "git":
        cmd = ["git", "clone", url, str(target)]
    else:
        raise ValueError(f"Unsupported method: {method}")
    _run(cmd)


def _update_dataset(target: Path, method: str) -> None:
    if method == "datalad" and shutil.which("datalad"):
        cmd = ["datalad", "update", "-d", str(target), "--how=merge", "--recursive"]
    else:
        cmd = ["git", "-C", str(target), "pull", "--ff-only"]
    _run(cmd)
