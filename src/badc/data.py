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
from typing import Any, Dict, List, Tuple

BADC_DATA_CONFIG = "BADC_DATA_CONFIG"


@dataclass(frozen=True)
class DatasetSpec:
    """Definition for a known dataset target."""

    name: str
    """Short name used on the CLI (e.g., ``bogus``)."""

    url: str
    """Clone URL for the dataset."""

    description: str = ""
    """Free-form description shown in docs/tests."""


@dataclass(frozen=True)
class SiblingInfo:
    """Description of a DataLad sibling reported by ``datalad siblings``."""

    name: str
    url: str | None
    push_url: str | None
    here: bool
    description: str | None = None
    status: str | None = None


@dataclass(frozen=True)
class DatasetStatus:
    """Filesystem + registry view for a tracked dataset."""

    name: str
    registry_status: str
    method: str
    path: Path | None
    exists: bool
    dataset_type: str
    notes: Tuple[str, ...]
    siblings: Tuple[SiblingInfo, ...]


DEFAULT_DATASETS: dict[str, DatasetSpec] = {
    "bogus": DatasetSpec(
        name="bogus",
        url="https://github.com/UBC-FRESH/badc-bogus-data.git",
        description="Lightweight public dataset for smoke-testing chunk/infer flows.",
    ),
}


def get_data_config_path() -> Path:
    """Return the path to the dataset registry TOML file.

    Returns
    -------
    Path
        ``~/.config/badc/data.toml`` by default or the location pointed to by
        ``BADC_DATA_CONFIG``.
    """

    env_path = os.environ.get(BADC_DATA_CONFIG)
    if env_path:
        return Path(env_path).expanduser()
    return Path.home() / ".config" / "badc" / "data.toml"


def load_data_config(config_path: Path | None = None) -> dict[str, Any]:
    """Load the dataset registry (if present).

    Parameters
    ----------
    config_path
        Optional custom path. When ``None``, :func:`get_data_config_path` is used.

    Returns
    -------
    dict
        Parsed TOML dictionary with at least a ``datasets`` key.
    """

    path = config_path or get_data_config_path()
    if not path.exists():
        return {"datasets": {}}
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    data.setdefault("datasets", {})
    return data


def save_data_config(config: dict[str, Any], config_path: Path | None = None) -> None:
    """Persist the registry to disk in TOML form.

    Parameters
    ----------
    config
        Dictionary produced by :func:`load_data_config` (or compatible structure).
    config_path
        Optional override location.
    """

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
    """Return the built-in dataset specification for ``name``.

    Parameters
    ----------
    name
        Dataset identifier (e.g., ``bogus``).

    Returns
    -------
    DatasetSpec
        The canonical specification.

    Raises
    ------
    KeyError
        If the dataset name is unknown.
    """

    if name not in DEFAULT_DATASETS:
        raise KeyError(name)
    return DEFAULT_DATASETS[name]


def available_method(preferred: str | None = None) -> str:
    """Determine which clone method to use.

    Parameters
    ----------
    preferred
        Optional user-provided choice (``git`` or ``datalad``).

    Returns
    -------
    str
        Method string to feed into the clone/update helpers.
    """

    if preferred:
        return preferred.lower()
    if shutil.which("datalad"):
        return "datalad"
    return "git"


def _run(cmd: list[str], cwd: Path | None = None) -> None:
    subprocess.run(cmd, cwd=cwd, check=True)


def _is_git_submodule(path: Path) -> bool:
    """Return ``True`` when ``path`` is managed as a git submodule."""

    git_path = path / ".git"
    if not git_path.exists() or git_path.is_dir():
        return False
    try:
        content = git_path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return False
    first_line = content.strip().splitlines()[0] if content else ""
    if not first_line.startswith("gitdir:"):
        return False
    gitdir = first_line.split(":", 1)[1].strip()
    normalized = Path(gitdir).as_posix()
    return "/.git/modules/" in normalized or normalized.endswith("/.git/modules")


def _is_datalad_dataset(path: Path) -> bool:
    return (path / ".datalad").exists()


def _dataset_type(path: Path) -> str:
    if _is_datalad_dataset(path):
        return "datalad"
    if (path / ".git").exists() or _is_git_submodule(path):
        return "git"
    return "unknown"


def _siblings_via_datalad(path: Path) -> tuple[list[SiblingInfo], str | None]:
    if not shutil.which("datalad"):
        return [], "datalad binary not available; skipping sibling inspection."
    try:
        result = subprocess.run(
            ["datalad", "-f", "json", "siblings", "-d", str(path)],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.strip() if exc.stderr else ""
        note = stderr or f"datalad siblings failed: {exc}"
        return [], note
    siblings: list[SiblingInfo] = []
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        name = payload.get("name") or "unknown"
        siblings.append(
            SiblingInfo(
                name=name,
                url=payload.get("url"),
                push_url=payload.get("pushurl"),
                here=payload.get("type") == "here" or bool(payload.get("here")),
                description=payload.get("description"),
                status=payload.get("state") or payload.get("status"),
            )
        )
    return siblings, None


def collect_dataset_statuses(
    show_siblings: bool = False,
    config_path: Path | None = None,
) -> List[DatasetStatus]:
    """Return registry entries annotated with filesystem information.

    Parameters
    ----------
    show_siblings
        When ``True`` and DataLad metadata is available, include sibling details.
    config_path
        Optional override for the registry location.
    """

    config = load_data_config(config_path)
    datasets: Dict[str, Dict[str, Any]] = config.get("datasets", {})
    statuses: List[DatasetStatus] = []
    for name in sorted(datasets):
        entry = datasets[name]
        path_value = entry.get("path")
        path = Path(path_value).expanduser() if path_value else None
        notes: List[str] = []
        siblings: List[SiblingInfo] = []
        exists = bool(path and path.exists())
        dataset_type = "unknown"
        if not path:
            notes.append("No path recorded; reconnect the dataset to capture its location.")
        else:
            if path.exists():
                dataset_type = _dataset_type(path)
                if show_siblings and dataset_type == "datalad":
                    sibling_list, sibling_note = _siblings_via_datalad(path)
                    siblings = sibling_list
                    if sibling_note:
                        notes.append(sibling_note)
                elif show_siblings and dataset_type != "datalad":
                    notes.append("Sibling inspection is only available for DataLad datasets.")
            else:
                notes.append(
                    f"Path {path} is missing; rerun `badc data connect {name}` to restore local files."
                )
        statuses.append(
            DatasetStatus(
                name=name,
                registry_status=entry.get("status", "unknown"),
                method=entry.get("method", "unknown"),
                path=path,
                exists=exists,
                dataset_type=dataset_type,
                notes=tuple(notes),
                siblings=tuple(siblings),
            )
        )
    return statuses


def connect_dataset(
    spec: DatasetSpec,
    target_dir: Path,
    *,
    method: str | None = None,
    pull_existing: bool = True,
    dry_run: bool = False,
    config_path: Path | None = None,
) -> str:
    """Clone or refresh ``spec`` into ``target_dir`` and record it.

    Parameters
    ----------
    spec
        Dataset definition (name + URL).
    target_dir
        Destination directory for the clone.
    method
        Optional override for ``git`` vs ``datalad`` (auto-detected otherwise).
    pull_existing
        When ``True``, run ``git pull``/``datalad update`` if the path already exists.
    dry_run
        When ``True``, compute the status but skip filesystem writes/registry updates.
    config_path
        Optional registry location.

    Returns
    -------
    str
        "cloned", "updated", or "exists" depending on the action performed.
    """

    target_dir = target_dir.expanduser()
    target_dir.parent.mkdir(parents=True, exist_ok=True)

    method_name = available_method(method)
    record_method = method_name
    target_exists = target_dir.exists()
    submodule_managed = target_exists and _is_git_submodule(target_dir)
    if submodule_managed:
        record_method = "git-submodule"
    status = ""

    if target_exists:
        if pull_existing and not submodule_managed:
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
            record_method,
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
    """Mark a dataset as disconnected and optionally delete its files.

    Parameters
    ----------
    name
        Dataset name recorded in the registry.
    dataset_path
        Filesystem location to remove/update.
    drop_content
        When ``True``, delete the directory (equivalent to ``datalad drop`` + ``rm``).
    dry_run
        Print the intended action without touching disk/config.
    config_path
        Optional registry location.

    Returns
    -------
    str
        "removed" when content is deleted, otherwise "detached".
    """

    dataset_path = dataset_path.expanduser()
    action = "detached"
    if drop_content and dataset_path.exists():
        action = "removed"
        if not dry_run:
            _drop_dataset_content(dataset_path)

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
    """Return the dataset registry.

    Parameters
    ----------
    config_path
        Optional override for the registry location.

    Returns
    -------
    dict
        Mapping of dataset name to metadata (path, url, status, etc.).
    """

    config = load_data_config(config_path)
    return config.get("datasets", {})


def resolve_dataset_path(
    name: str,
    base_path: Path,
    config_path: Path | None = None,
) -> Path:
    """Resolve the expected filesystem path for ``name``.

    Parameters
    ----------
    name
        Dataset identifier.
    base_path
        Base directory (e.g., ``data/datalad``) used when the registry lacks an entry.
    config_path
        Optional registry location.

    Returns
    -------
    Path
        Registered path or ``base_path / name`` when unknown.
    """

    datasets = list_tracked_datasets(config_path)
    entry = datasets.get(name)
    if entry and entry.get("path"):
        return Path(entry["path"])
    return base_path.expanduser() / name


def find_dataset_root(path: Path) -> Path | None:
    """Walk parents until a DataLad dataset (``.datalad``) is located.

    Parameters
    ----------
    path
        File or directory path inside (or near) a dataset.

    Returns
    -------
    Path or None
        Root directory containing ``.datalad`` or ``None`` when not found.
    """

    candidate = path.expanduser()
    if candidate.is_file():
        candidate = candidate.parent
    for current in [candidate, *candidate.parents]:
        if (current / ".datalad").exists():
            return current
    return None


def override_spec_url(spec: DatasetSpec, url: str | None) -> DatasetSpec:
    """Return a new spec with ``url`` overridden when provided.

    Parameters
    ----------
    spec
        Original dataset specification.
    url
        Replacement URL or ``None`` to keep the existing value.

    Returns
    -------
    DatasetSpec
        The original spec when ``url`` is ``None``; otherwise a clone with the new URL.
    """

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


def _drop_dataset_content(path: Path) -> None:
    """Remove dataset contents, preferring ``datalad drop`` when possible."""

    use_datalad = _is_datalad_dataset(path) and shutil.which("datalad")
    if use_datalad:
        _run(["datalad", "drop", "-d", str(path), "--recursive", "--reckless", "auto"])
    shutil.rmtree(path)
