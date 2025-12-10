"""Primary Typer CLI for the Bird Acoustic Data Compiler project."""

from __future__ import annotations

import json
import os
import queue
import shlex
import shutil
import subprocess
import threading
import time
import tomllib
from collections import defaultdict
from pathlib import Path
from typing import Annotated, Any, Optional, Sequence

import typer
from rich.console import Console, Group
from rich.live import Live
from rich.markup import escape
from rich.panel import Panel
from rich.table import Table

from badc import __version__, chunk_orchestrator, chunking, infer_orchestrator
from badc import data as data_utils
from badc.audio import get_wav_duration
from badc.chunk_writer import ChunkMetadata, iter_chunk_metadata
from badc.gpu import detect_gpus
from badc.hawkears_runner import JobExecutionError, run_job
from badc.infer_scheduler import GPUWorker, InferenceJob, load_jobs, plan_workers
from badc.telemetry import TelemetryRecord, default_log_path, load_telemetry

console = Console()
app = typer.Typer(help="Utilities for chunking and processing large bird audio corpora.")
DEFAULT_DATALAD_PATH = Path("data") / "datalad"
DEFAULT_INFER_OUTPUT = Path("artifacts") / "infer"

data_app = typer.Typer(help="Manage DataLad-backed audio repositories (stub commands).")
chunk_app = typer.Typer(help="Chunking utilities and HawkEars probe helpers.")
infer_app = typer.Typer(help="Inference + aggregation helpers (placeholder).")
report_app = typer.Typer(help="Reporting helpers built atop DuckDB/parquet detections.")
app.add_typer(data_app, name="data")
app.add_typer(chunk_app, name="chunk")
app.add_typer(infer_app, name="infer")
app.add_typer(report_app, name="report")


def _print_header() -> None:
    console.rule("Bird Acoustic Data Compiler")


def _load_infer_config(config_path: Path) -> dict[str, Any]:
    """Parse a TOML config describing a HawkEars inference run."""

    try:
        raw = config_path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:  # pragma: no cover - defensive
        raise typer.BadParameter(
            f"Config file {config_path} does not exist.", param_hint="config"
        ) from exc
    try:
        config = tomllib.loads(raw)
    except tomllib.TOMLDecodeError as exc:
        raise typer.BadParameter(f"Failed to parse {config_path}: {exc}") from exc

    runner_cfg = config.get("runner")
    if not isinstance(runner_cfg, dict):
        raise typer.BadParameter(
            "Config must define a [runner] table.", param_hint="[runner]"
        ) from None
    manifest = runner_cfg.get("manifest")
    if not manifest:
        raise typer.BadParameter(
            "Config [runner] section requires 'manifest'.", param_hint="runner.manifest"
        ) from None
    telemetry_log = runner_cfg.get("telemetry_log")
    hawkears_cfg = config.get("hawkears") or {}
    extra_args = hawkears_cfg.get("extra_args", [])
    if isinstance(extra_args, str):
        extra_args_list = [extra_args]
    elif isinstance(extra_args, list):
        extra_args_list = [str(arg) for arg in extra_args]
    elif extra_args in (None, {}):
        extra_args_list = []
    else:
        raise typer.BadParameter(
            "hawkears.extra_args must be a list of strings.",
            param_hint="hawkears.extra_args",
        ) from None
    return {
        "manifest": Path(manifest),
        "max_gpus": runner_cfg.get("max_gpus"),
        "output_dir": Path(runner_cfg.get("output_dir", DEFAULT_INFER_OUTPUT)),
        "runner_cmd": runner_cfg.get("runner_cmd"),
        "telemetry_log": Path(telemetry_log) if telemetry_log else None,
        "max_retries": runner_cfg.get("max_retries", 2),
        "use_hawkears": runner_cfg.get("use_hawkears", False),
        "hawkears_args": extra_args_list,
        "cpu_workers": runner_cfg.get("cpu_workers", 0),
    }


@app.command()
def version() -> None:
    """Display the current BADC version banner.

    Notes
    -----
    Uses ``rich`` styling to print the version header; primarily a smoke-test
    that the CLI installed correctly.
    """

    _print_header()
    console.print(f"BADC version: [bold]{__version__}[/]")


@data_app.command("connect")
def data_connect(
    name: Annotated[str, typer.Argument(help="Dataset name, e.g., 'bogus'.")],
    path: Annotated[
        Path,
        typer.Option("--path", help="Target path for the dataset.", dir_okay=True, file_okay=False),
    ] = Path("data/datalad"),
    url: Annotated[
        Optional[str],
        typer.Option("--url", help="Override dataset URL (required for unknown names)."),
    ] = None,
    method: Annotated[
        Optional[str],
        typer.Option("--method", help="Preferred clone method: git or datalad."),
    ] = None,
    pull_existing: Annotated[
        bool,
        typer.Option(
            "--pull/--no-pull",
            help="Update the dataset when it already exists locally.",
        ),
    ] = True,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run/--apply", help="Preview actions without running commands."),
    ] = False,
) -> None:
    """Clone or update a DataLad dataset and record its metadata.

    Parameters
    ----------
    name : str
        Registered dataset identifier (e.g., ``"bogus"``).
    path : Path
        Base directory where dataset folders are stored/created.
    url : str, optional
        Explicit clone URL for custom datasets; overrides the registry entry when
        provided.
    method : str, optional
        Preferred clone backend (``"git"`` or ``"datalad"``). ``None`` auto-detects
        based on tool availability.
    pull_existing : bool
        When ``True``, fetches updates if the dataset already exists locally.
    dry_run : bool
        If ``True``, prints the actions without cloning/updating or editing the config.

    Raises
    ------
    typer.BadParameter
        If the dataset is unknown and no URL is provided, or when an invalid method is
        supplied.
    typer.Exit
        Propagates ``subprocess.CalledProcessError`` return codes so Typer can exit
        cleanly.
    """

    method_normalized = method.lower() if method else None
    if method_normalized and method_normalized not in {"git", "datalad"}:
        raise typer.BadParameter("Method must be either 'git' or 'datalad'.", param_hint="--method")

    try:
        spec = data_utils.get_dataset_spec(name)
    except KeyError:
        if not url:
            raise typer.BadParameter(
                f"Unknown dataset '{name}'. Provide --url to supply a clone target.",
                param_hint="name",
            ) from None
        spec = data_utils.DatasetSpec(name=name, url=url, description="custom dataset")
    else:
        spec = data_utils.override_spec_url(spec, url)

    target_path = (path / name).expanduser()
    try:
        status = data_utils.connect_dataset(
            spec,
            target_path,
            method=method_normalized,
            pull_existing=pull_existing,
            dry_run=dry_run,
        )
    except subprocess.CalledProcessError as exc:
        console.print(f"[red]Failed to connect dataset:[/] {exc}", style="bold red")
        raise typer.Exit(code=exc.returncode) from exc
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc

    verb = {
        "cloned": "Cloned",
        "updated": "Updated",
        "exists": "Already present",
    }.get(status, status)
    dry_note = " (dry-run)" if dry_run else ""
    console.print(
        f"{verb} dataset [cyan]{name}[/] at [green]{target_path}[/]{dry_note}.",
        style="bold",
    )


@data_app.command("disconnect")
def data_disconnect(
    name: Annotated[str, typer.Argument(help="Dataset name to detach.")],
    drop_content: Annotated[
        bool,
        typer.Option(
            "--drop-content/--keep-content",
            help="When true, drop annexed files after disconnecting.",
        ),
    ] = False,
    path: Annotated[
        Path,
        typer.Option(
            "--path",
            help="Base directory that holds dataset folders (fallback when config is missing).",
            dir_okay=True,
            file_okay=False,
        ),
    ] = Path("data/datalad"),
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run/--apply", help="Preview actions without modifying files."),
    ] = False,
) -> None:
    """Mark a dataset as disconnected and optionally drop its contents.

    Parameters
    ----------
    name : str
        Dataset identifier to detach.
    drop_content : bool
        When ``True``, removes annexed content after marking the dataset disconnected.
    path : Path
        Base directory used to resolve the dataset path when it is missing from the
        config file.
    dry_run : bool
        If ``True``, prints the planned actions without touching files or configs.
    """

    dataset_path = data_utils.resolve_dataset_path(name, path)
    action = data_utils.disconnect_dataset(
        name,
        dataset_path,
        drop_content=drop_content,
        dry_run=dry_run,
    )
    drop_note = "removed" if action == "removed" else "retained"
    dry_note = " (dry-run)" if dry_run else ""
    console.print(
        f"Dataset [cyan]{name}[/] marked as disconnected; data {drop_note}{dry_note}.",
        style="bold",
    )


@data_app.command("status")
def data_status(
    details: Annotated[
        bool,
        typer.Option("--details/--summary", help="Show extended metadata for each dataset."),
    ] = False,
    show_siblings: Annotated[
        bool,
        typer.Option(
            "--show-siblings/--hide-siblings",
            help="Include `datalad siblings` output (requires DataLad).",
        ),
    ] = False,
) -> None:
    """Report all datasets tracked in ``~/.config/badc/data.toml``.

    Notes
    -----
    Useful for confirming which DataLad datasets are currently connected before running
    chunking or inference commands that rely on shared audio storage.
    """

    statuses = data_utils.collect_dataset_statuses(show_siblings=show_siblings)
    if not statuses:
        console.print("No datasets recorded. Run `badc data connect ...` first.")
        return

    if not details and not show_siblings:
        console.print("Tracked datasets:", style="bold")
        for entry in statuses:
            path_display = str(entry.path) if entry.path else "?"
            presence = "present" if entry.exists else "missing"
            presence_tag = escape(f"[{presence}]")
            console.print(
                f" - [cyan]{entry.name}[/]: {entry.registry_status} ({path_display}) {presence_tag}"
            )
        return

    for entry in statuses:
        path_display = str(entry.path) if entry.path else "?"
        presence = "yes" if entry.exists else "no"
        console.print(
            f"[cyan]{entry.name}[/] — {entry.registry_status} (method: {entry.method})",
            style="bold",
        )
        console.print(f"  Path: {path_display}")
        console.print(f"  Exists: {presence}; type: {entry.dataset_type}")
        for note in entry.notes:
            console.print(f"  Note: {escape(note)}", style="yellow")
        if show_siblings:
            if entry.siblings:
                console.print("  Siblings:")
                for sibling in entry.siblings:
                    parts = [sibling.name]
                    if sibling.here:
                        parts.append("[here]")
                    if sibling.status:
                        parts.append(f"state={sibling.status}")
                    if sibling.url:
                        parts.append(sibling.url)
                    elif sibling.push_url:
                        parts.append(sibling.push_url)
                    console.print("    - " + escape(" ".join(parts)))
            else:
                suffix = (
                    " (not a DataLad dataset)"
                    if entry.dataset_type != "datalad"
                    else " (no siblings reported)"
                )
                console.print(f"  Siblings: none{suffix}")


@chunk_app.command("probe")
def chunk_probe(
    file: Annotated[Path, typer.Argument(help="Path to the WAV file to probe.")],
    initial_duration: Annotated[
        float,
        typer.Option("--initial-duration", help="Starting chunk duration (seconds)."),
    ] = 60.0,
    max_duration: Annotated[
        float | None,
        typer.Option("--max-duration", help="Upper bound for the search window (seconds)."),
    ] = None,
    tolerance: Annotated[
        float,
        typer.Option("--tolerance", help="Stop when bounds differ by <= tolerance (seconds)."),
    ] = 5.0,
    gpu_index: Annotated[
        int | None,
        typer.Option("--gpu-index", help="GPU index to base estimates on (defaults to first GPU)."),
    ] = None,
    log_path: Annotated[
        Path | None,
        typer.Option(
            "--log",
            help="Telemetry log path (JSONL). Defaults to artifacts/telemetry/chunk_probe/<stem>_<timestamp>.jsonl.",
            dir_okay=False,
        ),
    ] = None,
) -> None:
    """Estimate chunk duration feasibility for a single audio file."""

    try:
        result = chunking.probe_chunk_duration(
            file,
            initial_duration,
            max_duration_s=max_duration,
            tolerance_s=tolerance,
            gpu_index=gpu_index,
            log_path=log_path,
        )
    except (ValueError, FileNotFoundError, RuntimeError) as exc:
        console.print(str(exc), style="red")
        raise typer.Exit(code=1) from exc

    console.print(
        f"Recommended chunk duration: [bold]{result.max_duration_s:.2f} s[/] "
        f"(strategy: {result.strategy})",
    )
    console.print(f"Notes: {result.notes}")
    if result.log_path:
        console.print(f"Telemetry log: {result.log_path}")
    if result.attempts:
        console.print("Recent attempts:")
        for attempt in result.attempts[-3:]:
            status = "[green]fits[/]" if attempt.fits else "[yellow]fails[/]"
            console.print(
                f" • {attempt.duration_s:.2f}s -> {attempt.estimated_vram_mb:.1f} MiB {status} ({attempt.reason})"
            )


@chunk_app.command("split")
def chunk_split(
    file: Annotated[Path, typer.Argument(help="Path to audio file to plan splits for.")],
    chunk_duration: Annotated[
        float,
        typer.Option("--chunk-duration", help="Desired chunk duration in seconds."),
    ] = 60.0,
) -> None:
    """List placeholder chunk identifiers for an audio file.

    Parameters
    ----------
    file : Path
        WAV file to inspect.
    chunk_duration : float
        Duration of each chunk in seconds.

    Notes
    -----
    This command does not write chunk files; it only previews identifiers so users can
    calibrate downstream expectations.
    """

    placeholders = list(chunking.iter_chunk_placeholders(file, chunk_duration))
    console.print(f"Planned {len(placeholders)} placeholder chunks for {file}:")
    for chunk_id in placeholders:
        console.print(f" - {chunk_id}")


@chunk_app.command("manifest")
def chunk_manifest(
    file: Annotated[Path, typer.Argument(help="Audio file to manifest.")],
    chunk_duration: Annotated[
        float,
        typer.Option("--chunk-duration", help="Chunk duration in seconds."),
    ] = 60.0,
    output: Annotated[
        Path,
        typer.Option("--output", help="Output CSV path.", file_okay=True, dir_okay=False),
    ] = Path("chunk_manifest.csv"),
    hash_chunks: Annotated[
        bool,
        typer.Option(
            "--hash-chunks/--no-hash-chunks",
            help="Compute SHA256 hashes for chunk entries (currently hashes entire file).",
        ),
    ] = False,
) -> None:
    """Create a manifest CSV describing fixed-duration chunks.

    Parameters
    ----------
    file : Path
        Source audio file to split.
    chunk_duration : float
        Desired chunk length in seconds.
    output : Path
        Destination CSV path for the manifest.
    hash_chunks : bool
        When ``True``, computes content hashes for each entry (currently the entire file)
        to support reproducibility checks.
    """

    duration = get_wav_duration(file)
    manifest_path = chunking.write_manifest(
        file,
        chunk_duration,
        output,
        duration,
        compute_hashes=hash_chunks,
    )
    console.print(
        f"Wrote manifest with chunk duration {chunk_duration}s to {manifest_path}"
        + (" (with hashes)" if hash_chunks else ""),
    )


@chunk_app.command("run")
def chunk_run(
    file: Annotated[Path, typer.Argument(help="Audio file to chunk.")],
    chunk_duration: Annotated[
        float,
        typer.Option("--chunk-duration", help="Chunk duration in seconds."),
    ],
    overlap: Annotated[
        float,
        typer.Option("--overlap", help="Overlap between chunks in seconds."),
    ] = 0.0,
    output_dir: Annotated[
        Path | None,
        typer.Option(
            "--output-dir",
            help=(
                "Directory for chunk files. Defaults to <dataset>/artifacts/chunks/<recording> "
                "when the source lives inside a DataLad dataset."
            ),
        ),
    ] = None,
    manifest: Annotated[
        Path | None,
        typer.Option(
            "--manifest",
            help=(
                "Manifest CSV path. Defaults to <dataset>/manifests/<recording>.csv when the "
                "source lives inside a DataLad dataset."
            ),
        ),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run/--write-chunks", help="Skip writing chunk files."),
    ] = False,
) -> None:
    """Write chunk WAVs (optional) and a manifest for downstream inference.

    Parameters
    ----------
    file : Path
        Source audio file to chunk.
    chunk_duration : float
        Desired duration of each chunk in seconds.
    overlap : float
        Overlap between consecutive chunks in seconds.
    output_dir : Path
        Directory where generated chunk WAVs should be stored. When omitted, defaults
        to ``<dataset>/artifacts/chunks/<recording>`` (or ``<audio_parent>/artifacts/chunks/<recording>``
        outside of DataLad datasets).
    manifest : Path
        Output manifest CSV path. Defaults to ``<dataset>/manifests/<recording>.csv`` when a
        DataLad dataset is detected or ``<audio_parent>/manifests/<recording>.csv`` otherwise.
    dry_run : bool
        When ``True``, skips writing chunk files and emits mock metadata for planning.

    Notes
    -----
    Hashes are only computed when chunk files are actually written. Dry runs help plan
    output layouts without touching disk.
    """

    file = file.expanduser().resolve()
    dataset_root = data_utils.find_dataset_root(file)
    duration = get_wav_duration(file)
    resolved_output_dir = (
        _resolve_cli_path(output_dir, dataset_root)
        if output_dir
        else _default_chunk_output_dir(file, dataset_root)
    )
    resolved_manifest = (
        _resolve_cli_path(manifest, dataset_root)
        if manifest
        else _default_manifest_path(file, dataset_root)
    )
    overlap_ms = int(max(overlap, 0.0) * 1000)
    if dry_run:
        chunk_rows = _build_dry_run_metadata(
            file=file,
            chunk_duration=chunk_duration,
            overlap_ms=overlap_ms,
            duration_s=duration,
            output_dir=resolved_output_dir,
        )
    else:
        chunk_rows = list(
            iter_chunk_metadata(
                audio_path=file,
                chunk_duration_s=chunk_duration,
                overlap_s=overlap,
                output_dir=resolved_output_dir,
            )
        )
    if not chunk_rows:
        console.print("No chunks generated.", style="yellow")
        return
    manifest_path = chunking.write_manifest(
        file,
        chunk_duration,
        resolved_manifest,
        duration,
        compute_hashes=not dry_run,
        chunk_rows=chunk_rows,
    )
    console.print(
        f"Chunks {'skipped' if dry_run else f'written to {resolved_output_dir}'}; "
        f"manifest at {manifest_path}"
    )


def _resolve_cli_path(path: Path, dataset_root: Path | None) -> Path:
    """Return an absolute path, rebasing relative paths to the dataset root when available."""

    expanded = path.expanduser()
    if dataset_root and not expanded.is_absolute():
        return (dataset_root / expanded).resolve()
    if expanded.is_absolute():
        return expanded
    return (Path.cwd() / expanded).resolve()


def _default_chunk_output_dir(file: Path, dataset_root: Path | None) -> Path:
    """Compute the default chunk directory for ``file``."""

    base = dataset_root or file.parent
    return base / "artifacts" / "chunks" / file.stem


def _default_manifest_path(file: Path, dataset_root: Path | None) -> Path:
    """Compute the default manifest path for ``file``."""

    base = dataset_root or file.parent
    return base / "manifests" / f"{file.stem}.csv"


def _build_dry_run_metadata(
    *,
    file: Path,
    chunk_duration: float,
    overlap_ms: int,
    duration_s: float,
    output_dir: Path,
) -> list[ChunkMetadata]:
    """Return deterministic chunk metadata without writing files."""

    rows: list[ChunkMetadata] = []
    for start, end in chunking.plan_chunk_ranges(duration_s, chunk_duration):
        start_ms = int(start * 1000)
        end_ms = int(end * 1000)
        chunk_id = f"{file.stem}_chunk_{start_ms}_{end_ms}"
        chunk_path = output_dir / f"{chunk_id}.wav"
        rows.append(
            ChunkMetadata(
                chunk_id=chunk_id,
                path=chunk_path,
                start_ms=start_ms,
                end_ms=end_ms,
                overlap_ms=overlap_ms,
                sha256="DRY_RUN",
            )
        )
    return rows


def _can_record_with_datalad(dataset_root: Path) -> bool:
    """Return True when `datalad run` should be used for chunk application."""

    if os.environ.get("BADC_DISABLE_DATALAD"):
        return False
    return (dataset_root / ".datalad").exists() and shutil.which("datalad") is not None


@chunk_app.command("orchestrate")
def chunk_orchestrate(
    dataset: Annotated[
        Path,
        typer.Argument(help="DataLad dataset that contains audio/ recordings."),
    ] = Path("data/datalad/bogus"),
    pattern: Annotated[
        str,
        typer.Option("--pattern", help="Glob used to select source audio files."),
    ] = "*.wav",
    chunk_duration: Annotated[
        float,
        typer.Option("--chunk-duration", help="Chunk duration (seconds)."),
    ] = 60.0,
    overlap: Annotated[
        float,
        typer.Option("--overlap", help="Overlap between chunks (seconds)."),
    ] = 0.0,
    manifest_dir: Annotated[
        Path,
        typer.Option("--manifest-dir", help="Directory for manifest CSVs (relative to dataset)."),
    ] = Path("manifests"),
    chunks_dir: Annotated[
        Path,
        typer.Option("--chunks-dir", help="Directory for chunk WAVs (relative to dataset)."),
    ] = Path("artifacts/chunks"),
    include_existing: Annotated[
        bool,
        typer.Option(
            "--include-existing/--skip-existing",
            help="Include recordings that already have manifests.",
        ),
    ] = False,
    limit: Annotated[
        int,
        typer.Option("--limit", help="Cap number of planned recordings."),
    ] = 0,
    print_datalad_run: Annotated[
        bool,
        typer.Option(
            "--print-datalad-run",
            help="Show per-recording `datalad run` commands instead of just the summary table.",
        ),
    ] = False,
    apply: Annotated[
        bool,
        typer.Option(
            "--apply/--plan-only",
            help="Execute badc chunk run for every plan instead of printing only.",
        ),
    ] = False,
    plan_csv: Annotated[
        Path | None,
        typer.Option("--plan-csv", help="Optional CSV path to save the generated plan."),
    ] = None,
    plan_json: Annotated[
        Path | None,
        typer.Option("--plan-json", help="Optional JSON path to save the generated plan."),
    ] = None,
    record_datalad: Annotated[
        bool,
        typer.Option(
            "--record-datalad/--no-record-datalad",
            help="When applying, wrap each chunk in `datalad run` if possible.",
        ),
    ] = True,
) -> None:
    """Plan chunk jobs across an entire dataset without touching audio files."""

    dataset = dataset.expanduser()
    try:
        plans = chunk_orchestrator.build_chunk_plan(
            dataset,
            pattern=pattern,
            chunk_duration=chunk_duration,
            overlap=overlap,
            manifest_dir=manifest_dir,
            chunks_dir=chunks_dir,
            include_existing=include_existing,
            limit=limit or None,
        )
    except FileNotFoundError as exc:
        console.print(str(exc), style="red")
        raise typer.Exit(code=1) from exc

    if not plans:
        console.print("No recordings matched the provided criteria.", style="yellow")
        return

    table = Table(title="Chunk plan", expand=True)
    table.add_column("Recording")
    table.add_column("Audio")
    table.add_column("Manifest")
    table.add_column("Chunks dir")
    for plan in plans:
        table.add_row(
            plan.recording_id,
            str(plan.audio_path),
            str(plan.manifest_path),
            str(plan.chunk_output_dir),
        )
    console.print(table)
    if plan_csv or plan_json:
        records = [plan.to_dict() for plan in plans]
        if plan_csv:
            plan_csv.parent.mkdir(parents=True, exist_ok=True)
            headers = list(records[0].keys())
            lines = [",".join(headers)]
            for record in records:
                lines.append(",".join(str(record[h]) for h in headers))
            plan_csv.write_text("\n".join(lines) + "\n")
            console.print(f"Saved plan CSV to {plan_csv}")
        if plan_json:
            import json

            plan_json.parent.mkdir(parents=True, exist_ok=True)
            plan_json.write_text(json.dumps(records, indent=2))
            console.print(f"Saved plan JSON to {plan_json}")

    if print_datalad_run:
        console.print("\nDatalad commands (run from dataset root):", style="bold")
        for plan in plans:
            command = chunk_orchestrator.render_datalad_run(plan, dataset)
            console.print(f" - {command}")
    if apply:
        console.print("\nApplying chunk plan…", style="bold")
        use_datalad = record_datalad and _can_record_with_datalad(dataset)
        if record_datalad and not use_datalad:
            console.print(
                "Datalad execution requested but not available (missing `.datalad` or `datalad` executable). "
                "Falling back to direct chunk runs.",
                style="yellow",
            )
        for plan in plans:
            console.print(f"[cyan]Chunking {plan.recording_id}[/]")
            if use_datalad:
                command = chunk_orchestrator.render_datalad_run(plan, dataset)
                try:
                    subprocess.run(shlex.split(command), cwd=dataset, check=True)
                except subprocess.CalledProcessError as exc:
                    console.print(
                        f"Chunking failed for {plan.recording_id}: {exc}",
                        style="red",
                    )
                    raise typer.Exit(code=exc.returncode) from exc
            else:
                chunk_run(
                    file=plan.audio_path,
                    chunk_duration=plan.chunk_duration,
                    overlap=plan.overlap,
                    output_dir=plan.chunk_output_dir,
                    manifest=plan.manifest_path,
                    dry_run=False,
                )


@app.command("gpus")
def list_gpus() -> None:
    """Display GPU inventory as reported by ``nvidia-smi``.

    Notes
    -----
    Provides a quick sanity check before running inference so operators know how many
    worker threads to request via ``--max-gpus`` or ``--cpu-workers``.
    """

    detection = detect_gpus()
    if detection.diagnostic:
        console.print(detection.diagnostic, style="yellow")
    infos = detection.gpus
    if not infos:
        console.print("No GPUs detected via nvidia-smi.", style="yellow")
        return
    console.print("Detected GPUs:")
    for info in infos:
        console.print(f" - #{info.index}: {info.name} ({info.memory_total_mb} MiB)")


@infer_app.command("run")
def infer_run(
    manifest: Annotated[Path, typer.Argument(help="Path to chunk manifest CSV.")],
    max_gpus: Annotated[
        int | None,
        typer.Option("--max-gpus", help="Limit number of GPUs to use."),
    ] = None,
    output_dir: Annotated[
        Path,
        typer.Option("--output-dir", help="Directory for inference outputs."),
    ] = Path("artifacts/infer"),
    runner_cmd: Annotated[
        str | None,
        typer.Option("--runner-cmd", help="Command used to invoke HawkEars (default stub)."),
    ] = None,
    telemetry_log: Annotated[
        Path | None,
        typer.Option("--telemetry-log", help="Telemetry log path (JSONL)."),
    ] = None,
    max_retries: Annotated[
        int,
        typer.Option("--max-retries", help="Maximum retries per chunk."),
    ] = 2,
    use_hawkears: Annotated[
        bool,
        typer.Option(
            "--use-hawkears/--stub-runner",
            help="Invoke the embedded HawkEars analyze.py script instead of the stub runner.",
        ),
    ] = False,
    hawkears_arg: Annotated[
        list[str] | None,
        typer.Option(
            "--hawkears-arg",
            help="Extra argument to pass to HawkEars analyze.py (repeatable).",
        ),
    ] = None,
    cpu_workers: Annotated[
        int,
        typer.Option(
            "--cpu-workers",
            help="Additional CPU worker threads (always at least one when GPUs are unavailable).",
        ),
    ] = 0,
    print_datalad_run: Annotated[
        bool,
        typer.Option(
            "--print-datalad-run",
            help="Show a ready-to-run `datalad run` command (no inference executed).",
        ),
    ] = False,
    resume_summary: Annotated[
        Path | None,
        typer.Option(
            "--resume-summary",
            help="Skip chunks already marked success in this scheduler summary JSON.",
        ),
    ] = None,
) -> None:
    """Run HawkEars (or a custom runner) for every chunk in a manifest.

    Parameters
    ----------
    manifest : Path
        CSV describing chunk jobs (generated by ``badc chunk manifest`` or ``chunk run``).
    max_gpus : int, optional
        Optional cap on GPUs to assign; defaults to auto-detecting all available GPUs.
    output_dir : Path
        Directory (or dataset-relative folder) where inference outputs should be stored.
    runner_cmd : str, optional
        Custom command that processes a chunk. Mutually exclusive with ``--use-hawkears``.
    max_retries : int
        Maximum number of attempts per chunk before marking it failed.
    use_hawkears : bool
        Toggle to invoke ``vendor/HawkEars/analyze.py`` directly instead of the stub
        runner.
    hawkears_arg : list[str], optional
        Extra CLI flags forwarded verbatim to HawkEars.
    cpu_workers : int
        Number of additional CPU worker threads to schedule alongside detected
        GPUs. When no GPUs are detected, at least one CPU worker is added.
    print_datalad_run : bool
        Emits a ``datalad run`` command instead of executing inference.

    Raises
    ------
    typer.BadParameter
        If mutually exclusive options are supplied or chunk roots span multiple
        DataLad datasets when ``--print-datalad-run`` is used.
    """

    if runner_cmd and use_hawkears:
        raise typer.BadParameter(
            "Use either --runner-cmd or --use-hawkears, not both.", param_hint="runner"
        )

    jobs = load_jobs(manifest)
    resume_entries: set[tuple[str | None, str]] = set()
    if resume_summary:
        resume_entries = _load_resume_chunks(resume_summary)
        if resume_entries:
            console.print(
                f"Resume summary {resume_summary} has {len(resume_entries)} completed chunk(s).",
                style="yellow",
            )
    extra_args = hawkears_arg or []
    workers, detection_note = plan_workers(max_gpus=max_gpus)
    if detection_note:
        console.print(detection_note, style="yellow")
    if resume_entries:
        before = len(jobs)
        jobs = [job for job in jobs if not _should_skip_job(job, resume_entries)]
        skipped = before - len(jobs)
        if skipped:
            console.print(f"Skipping {skipped} chunk(s) already completed.", style="yellow")
        orphaned = len(resume_entries) - skipped
        if orphaned > 0:
            console.print(
                f"{orphaned} chunk entry(ies) from the summary were not present in this manifest.",
                style="yellow",
            )
    if not jobs:
        if resume_entries:
            console.print(
                "All chunks in this manifest are already marked complete in the resume summary.",
                style="yellow",
            )
        else:
            console.print("No jobs found in manifest.", style="yellow")
        return

    worker_slots: list[tuple[GPUWorker | None, str]] = []
    for gpu_worker in workers:
        worker_slots.append((gpu_worker, f"gpu-{gpu_worker.index}"))
    if not worker_slots:
        cpu_slot_count = max(cpu_workers, 1)
        console.print(
            f"No GPUs detected; running on CPU with {cpu_slot_count} worker(s).",
            style="yellow",
        )
    else:
        cpu_slot_count = max(0, cpu_workers)
        if cpu_slot_count:
            console.print(
                f"Adding {cpu_slot_count} CPU worker(s) alongside {len(worker_slots)} GPU worker(s).",
                style="yellow",
            )
    for idx in range(cpu_slot_count):
        worker_slots.append((None, f"cpu-{idx}"))
    if not worker_slots:
        worker_slots = [(None, "cpu-0")]
    default_output = output_dir.expanduser()
    use_dataset_outputs = default_output == DEFAULT_INFER_OUTPUT
    job_contexts = _prepare_job_contexts(jobs, default_output, use_dataset_outputs)
    telemetry_base: Path | None = None
    if telemetry_log is None and use_dataset_outputs and job_contexts:
        first_root = job_contexts[0][2]
        if first_root:
            telemetry_base = first_root / "artifacts" / "telemetry"
    telemetry_path = telemetry_log or default_log_path(manifest, base_dir=telemetry_base)

    if print_datalad_run:
        _print_datalad_run_instructions(
            manifest=manifest,
            job_contexts=job_contexts,
            max_gpus=max_gpus,
            output_dir=default_output,
            runner_cmd=runner_cmd,
            telemetry_log=telemetry_path,
            max_retries=max_retries,
            use_hawkears=use_hawkears,
            hawkears_args=extra_args,
            cpu_workers=cpu_workers,
            resume_summary=resume_summary,
        )
        return

    console.print(f"Telemetry log: {telemetry_path}")
    scheduler_summary = _run_scheduler(
        job_contexts=job_contexts,
        worker_pool=worker_slots,
        runner_cmd=runner_cmd,
        max_retries=max_retries,
        use_hawkears=use_hawkears,
        hawkears_args=extra_args,
        telemetry_path=telemetry_path,
    )
    worker_summary = scheduler_summary["workers"]
    _write_scheduler_summary(
        telemetry_path=telemetry_path,
        job_summary=scheduler_summary["jobs"],
        worker_summary=worker_summary,
    )
    output_locations = sorted({ctx[1] for ctx in job_contexts})
    if len(output_locations) == 1:
        location_msg = str(output_locations[0])
    else:
        display = ", ".join(str(p) for p in output_locations[:3])
        if len(output_locations) > 3:
            display += ", ..."
        location_msg = display
    console.print(f"Processed {len(jobs)} jobs; outputs stored in {location_msg}")
    if worker_summary:
        summary_table = Table(title="Worker summary", expand=False)
        summary_table.add_column("Worker")
        summary_table.add_column("Jobs", justify="right")
        summary_table.add_column("Failures", justify="right")
        summary_table.add_column("Retries", justify="right")
        summary_table.add_column("Failed attempts", justify="right")
        for label, counts in sorted(worker_summary.items()):
            total = counts["success"] + counts["failure"]
            summary_table.add_row(
                label,
                str(total),
                str(counts["failure"]),
                str(counts.get("retries", 0)),
                str(counts.get("failed_retries", 0)),
            )
        console.print(summary_table)


@infer_app.command("orchestrate")
def infer_orchestrate(
    dataset: Annotated[
        Path,
        typer.Argument(help="DataLad dataset containing manifests/chunks."),
    ] = Path("data/datalad/bogus"),
    manifest_dir: Annotated[
        Path,
        typer.Option("--manifest-dir", help="Directory that stores chunk manifests."),
    ] = Path("manifests"),
    pattern: Annotated[
        str,
        typer.Option("--pattern", help="Glob used to select manifests."),
    ] = "*.csv",
    output_dir: Annotated[
        Path,
        typer.Option("--output-dir", help="Root directory for inference outputs."),
    ] = Path("artifacts/infer"),
    telemetry_dir: Annotated[
        Path,
        typer.Option("--telemetry-dir", help="Directory for telemetry logs."),
    ] = Path("artifacts/telemetry"),
    chunk_plan: Annotated[
        Path | None,
        typer.Option("--chunk-plan", help="Optional chunk plan CSV/JSON to source manifests."),
    ] = None,
    include_existing: Annotated[
        bool,
        typer.Option(
            "--include-existing/--skip-existing",
            help="Include manifests that already have inference outputs.",
        ),
    ] = False,
    limit: Annotated[
        int,
        typer.Option("--limit", help="Cap number of planned manifests."),
    ] = 0,
    max_gpus: Annotated[
        int | None,
        typer.Option("--max-gpus", help="Max GPUs to set in the plan/apply step."),
    ] = None,
    use_hawkears: Annotated[
        bool,
        typer.Option(
            "--use-hawkears/--stub-runner",
            help="Use HawkEars analyze.py in the generated plan.",
        ),
    ] = True,
    hawkears_arg: Annotated[
        list[str] | None,
        typer.Option("--hawkears-arg", help="Extra HawkEars args to bake into the plan."),
    ] = None,
    print_datalad_run: Annotated[
        bool,
        typer.Option(
            "--print-datalad-run",
            help="Print `datalad run` commands for each manifest.",
        ),
    ] = False,
    apply: Annotated[
        bool,
        typer.Option(
            "--apply/--plan-only",
            help="Execute badc infer run for every plan.",
        ),
    ] = False,
    plan_csv: Annotated[
        Path | None,
        typer.Option("--plan-csv", help="Optional CSV path to save the inference plan."),
    ] = None,
    plan_json: Annotated[
        Path | None,
        typer.Option("--plan-json", help="Optional JSON path to save the inference plan."),
    ] = None,
    cpu_workers: Annotated[
        int,
        typer.Option(
            "--cpu-workers",
            help="Additional CPU worker threads to include in each run (in addition to GPUs).",
        ),
    ] = 0,
    record_datalad: Annotated[
        bool,
        typer.Option(
            "--record-datalad/--no-record-datalad",
            help="Wrap applied runs in `datalad run` when possible.",
        ),
    ] = True,
    sockeye_script: Annotated[
        Path | None,
        typer.Option(
            "--sockeye-script",
            help="Optional path to write a Sockeye SLURM array script for the generated plan.",
        ),
    ] = None,
    sockeye_job_name: Annotated[
        str,
        typer.Option("--sockeye-job-name", help="Job name used in the generated Sockeye script."),
    ] = "badc-infer",
    sockeye_account: Annotated[
        str | None,
        typer.Option("--sockeye-account", help="Account name for Sockeye `#SBATCH --account`."),
    ] = None,
    sockeye_partition: Annotated[
        str | None,
        typer.Option(
            "--sockeye-partition", help="Partition (`#SBATCH --partition`) used in the script."
        ),
    ] = None,
    sockeye_gres: Annotated[
        str | None,
        typer.Option("--sockeye-gres", help="`#SBATCH --gres` value, e.g., gpu:2."),
    ] = None,
    sockeye_time: Annotated[
        str | None,
        typer.Option("--sockeye-time", help="Walltime limit for the script (e.g., 04:00:00)."),
    ] = None,
    sockeye_cpus_per_task: Annotated[
        int | None,
        typer.Option("--sockeye-cpus-per-task", help="`#SBATCH --cpus-per-task` value."),
    ] = None,
    sockeye_mem: Annotated[
        str | None,
        typer.Option("--sockeye-mem", help="`#SBATCH --mem` value (e.g., 64G)."),
    ] = None,
    resume_completed: Annotated[
        bool,
        typer.Option(
            "--resume-completed/--rerun-all",
            help="When applying, reuse existing telemetry summaries to skip completed chunks.",
        ),
    ] = False,
    sockeye_resume_completed: Annotated[
        bool,
        typer.Option(
            "--sockeye-resume-completed/--sockeye-rerun-all",
            help="When generating Sockeye scripts, add --resume-summary if prior telemetry summaries exist.",
        ),
    ] = False,
) -> None:
    """Plan inference runs across manifests without executing them."""

    dataset = dataset.expanduser()
    manifest_paths: list[Path] | None = None
    if chunk_plan:
        manifest_paths = infer_orchestrator.load_manifest_paths_from_plan(chunk_plan)
    plans = infer_orchestrator.build_infer_plan(
        dataset,
        manifest_paths=manifest_paths,
        manifest_dir=manifest_dir,
        pattern=pattern,
        output_dir=output_dir,
        telemetry_dir=telemetry_dir,
        include_existing=include_existing,
        use_hawkears=use_hawkears,
        hawkears_args=hawkears_arg,
        max_gpus=max_gpus,
        cpu_workers=cpu_workers,
        limit=limit or None,
    )
    if not plans:
        console.print("No manifests matched the provided criteria.", style="yellow")
        return
    table = Table(title="Inference plan", expand=True)
    table.add_column("Recording")
    table.add_column("Manifest")
    table.add_column("Output dir")
    table.add_column("Telemetry log")
    for plan in plans:
        table.add_row(
            plan.recording_id,
            str(plan.manifest_path),
            str(plan.recording_output),
            str(plan.telemetry_log),
        )
    console.print(table)

    if plan_csv or plan_json:
        records = [plan.to_dict() for plan in plans]
        if plan_csv:
            plan_csv.parent.mkdir(parents=True, exist_ok=True)
            headers = list(records[0].keys())
            lines = [",".join(headers)]
            for record in records:
                lines.append(",".join(str(record[h]) for h in headers))
            plan_csv.write_text("\n".join(lines) + "\n")
            console.print(f"Saved inference plan CSV to {plan_csv}")
        if plan_json:
            plan_json.parent.mkdir(parents=True, exist_ok=True)
            plan_json.write_text(json.dumps(records, indent=2))
            console.print(f"Saved inference plan JSON to {plan_json}")

    if sockeye_script:
        script = _render_sockeye_script(
            dataset,
            plans,
            job_name=sockeye_job_name,
            account=sockeye_account,
            partition=sockeye_partition,
            gres=sockeye_gres,
            time_limit=sockeye_time,
            cpus_per_task=sockeye_cpus_per_task,
            mem=sockeye_mem,
            resume_completed=sockeye_resume_completed,
        )
        sockeye_script.parent.mkdir(parents=True, exist_ok=True)
        sockeye_script.write_text(script)
        console.print(f"Wrote Sockeye array script to {sockeye_script}")

    if print_datalad_run:
        console.print("\nDatalad commands (run from dataset root):", style="bold")
        for plan in plans:
            command = infer_orchestrator.render_datalad_run(plan, dataset)
            console.print(f" - {command}")

    if apply:
        console.print("\nExecuting inference plan…", style="bold")
        use_datalad = record_datalad and _can_record_with_datalad(dataset)
        if record_datalad and not use_datalad:
            console.print(
                "Datalad execution requested but not available (missing `.datalad` or `datalad` executable). "
                "Falling back to direct inference runs.",
                style="yellow",
            )
        for plan in plans:
            console.print(f"[cyan]Inferring {plan.recording_id}[/]")
            plan.telemetry_log.parent.mkdir(parents=True, exist_ok=True)
            plan.output_dir.mkdir(parents=True, exist_ok=True)
            resume_arg: Path | None = None
            if resume_completed:
                summary_path = _telemetry_summary_path(plan.telemetry_log)
                if summary_path.exists():
                    resume_arg = summary_path
                    console.print(
                        f"Resume enabled; skipping completed chunks via {summary_path}.",
                        style="yellow",
                    )
                else:
                    console.print(
                        f"Resume enabled but no summary at {summary_path}; running full manifest.",
                        style="yellow",
                    )
            if use_datalad:
                command = infer_orchestrator.render_datalad_run(
                    plan, dataset, resume_summary=resume_arg
                )
                try:
                    subprocess.run(shlex.split(command), cwd=dataset, check=True)
                except subprocess.CalledProcessError as exc:
                    console.print(
                        f"Inference failed for {plan.recording_id}: {exc}",
                        style="red",
                    )
                    raise typer.Exit(code=exc.returncode) from exc
            else:
                infer_run(
                    manifest=plan.manifest_path,
                    max_gpus=plan.max_gpus,
                    output_dir=plan.output_dir,
                    telemetry_log=plan.telemetry_log,
                    use_hawkears=plan.use_hawkears,
                    hawkears_arg=list(plan.hawkears_args),
                    cpu_workers=plan.cpu_workers,
                    resume_summary=resume_arg,
                )


@infer_app.command("run-config")
def infer_run_config(
    config: Annotated[
        Path, typer.Argument(help="Path to a TOML config (see configs/hawkears-*.toml).")
    ],
    print_datalad_run: Annotated[
        bool,
        typer.Option(
            "--print-datalad-run",
            help="Show the underlying `datalad run` command instead of executing inference.",
        ),
    ] = False,
) -> None:
    """Execute ``badc infer run`` using a TOML configuration file."""

    settings = _load_infer_config(config)
    infer_run(
        manifest=settings["manifest"],
        max_gpus=settings["max_gpus"],
        output_dir=settings["output_dir"],
        runner_cmd=settings["runner_cmd"],
        telemetry_log=settings["telemetry_log"],
        max_retries=settings["max_retries"],
        use_hawkears=settings["use_hawkears"],
        hawkears_arg=settings["hawkears_args"],
        cpu_workers=settings["cpu_workers"],
        print_datalad_run=print_datalad_run,
    )


def _run_scheduler(
    job_contexts: Sequence[tuple[InferenceJob, Path, Path | None]],
    worker_pool: Sequence[tuple[GPUWorker | None, str]],
    runner_cmd: str | None,
    max_retries: int,
    use_hawkears: bool,
    hawkears_args: Sequence[str],
    telemetry_path: Path,
) -> dict[str, dict]:
    """Dispatch inference jobs to worker threads.

    Parameters
    ----------
    job_contexts : Sequence[tuple[InferenceJob, Path, Path | None]]
        Each tuple contains the job metadata, the output directory, and the optional
        dataset root used for provenance tracking.
    worker_pool : Sequence[tuple[GPUWorker | None, str]]
        Worker definitions (``None`` entries represent CPU-only workers). Each
        tuple pairs the worker with a label that is surfaced in the summary table.
    runner_cmd : str, optional
        Custom command to execute per chunk when ``use_hawkears`` is ``False``.
    max_retries : int
        Number of times to retry a failing job before surfacing the exception.
    use_hawkears : bool
        When ``True``, invokes the vendored HawkEars analyzer instead of the stub.
    hawkears_args : Sequence[str]
        Additional CLI arguments forwarded to HawkEars.

    Returns
    -------
    dict
        Includes ``workers`` (per-worker statistics) and ``jobs`` (per-chunk
        outcomes) so resume logic can identify which chunks succeeded.

    Raises
    ------
    Exception
        Re-raises the first worker failure after shutting down the pool.
    """

    if not worker_pool:
        worker_pool = [(None, "cpu-0")]
    job_queue: queue.Queue = queue.Queue()
    sentinel = object()
    for context in job_contexts:
        job_queue.put(context)
    for _ in worker_pool:
        job_queue.put(sentinel)

    stop_event = threading.Event()
    errors: list[Exception] = []
    runner_args = list(hawkears_args)
    stats: dict[str, dict[str, int]] = {
        label: {"success": 0, "failure": 0, "retries": 0, "failed_retries": 0}
        for _, label in worker_pool
    }
    stats_lock = threading.Lock()
    job_results: dict[str, dict[str, object]] = {}
    job_lock = threading.Lock()

    def worker_loop(worker_entry: tuple[GPUWorker | None, str]) -> None:
        worker, label = worker_entry
        while True:
            item = job_queue.get()
            try:
                if item is sentinel:
                    return
                if stop_event.is_set():
                    continue
                job, job_output, dataset_root = item
                job_result = run_job(
                    job=job,
                    worker=worker,  # type: ignore[arg-type]
                    output_dir=job_output,
                    runner_cmd=runner_cmd,
                    max_retries=max_retries,
                    use_hawkears=use_hawkears,
                    hawkears_args=runner_args,
                    dataset_root=dataset_root,
                    telemetry_path=telemetry_path,
                )
                with stats_lock:
                    stats[label]["success"] += 1
                    stats[label]["retries"] += getattr(job_result, "retries", 0)
                with job_lock:
                    job_results[job.chunk_id] = {
                        "status": "success",
                        "attempts": getattr(job_result, "attempts", None),
                        "retries": getattr(job_result, "retries", None),
                        "output": str(getattr(job_result, "output_path", job_output)),
                        "worker": label,
                        "recording_id": job.recording_id,
                    }
            except Exception as exc:  # pragma: no cover - propagated to main thread
                errors.append(exc)
                stop_event.set()
                with stats_lock:
                    stats[label]["failure"] += 1
                    if isinstance(exc, JobExecutionError):
                        stats[label]["failed_retries"] += max(exc.attempts - 1, 0)
                with job_lock:
                    job_results[job.chunk_id] = {
                        "status": "failure",
                        "error": str(exc),
                        "attempts": getattr(exc, "attempts", None),
                        "worker": label,
                        "recording_id": job.recording_id,
                    }
            finally:
                job_queue.task_done()

    threads = [
        threading.Thread(target=worker_loop, args=(worker,), daemon=True) for worker in worker_pool
    ]
    for thread in threads:
        thread.start()
    job_queue.join()
    for thread in threads:
        thread.join()
    if errors:
        raise errors[0]
    return {"workers": stats, "jobs": job_results}


def _write_scheduler_summary(
    *,
    telemetry_path: Path,
    job_summary: dict[str, dict[str, object]],
    worker_summary: dict[str, dict[str, int]],
) -> None:
    """Persist scheduler metadata alongside the telemetry log for resume workflows."""

    summary_path = _telemetry_summary_path(telemetry_path)
    payload = {
        "telemetry_log": str(telemetry_path),
        "workers": worker_summary,
        "jobs": job_summary,
    }
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    console.print(f"Scheduler summary: {summary_path}")


def _telemetry_summary_path(telemetry_path: Path) -> Path:
    return telemetry_path.with_suffix(telemetry_path.suffix + ".summary.json")


def _load_resume_chunks(summary_path: Path) -> set[tuple[str | None, str]]:
    summary_path = summary_path.expanduser()
    try:
        raw = summary_path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:  # pragma: no cover - defensive
        raise typer.BadParameter(
            f"Resume summary {summary_path} does not exist.", param_hint="resume-summary"
        ) from exc
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise typer.BadParameter(
            f"Failed to parse resume summary {summary_path}: {exc}", param_hint="resume-summary"
        ) from exc
    jobs = data.get("jobs") or {}
    entries: set[tuple[str | None, str]] = set()
    for chunk_id, meta in jobs.items():
        if not isinstance(meta, dict):
            continue
        if meta.get("status") != "success":
            continue
        recording_id = meta.get("recording_id")
        entries.add((recording_id, chunk_id))
    return entries


def _should_skip_job(job: InferenceJob, resume_entries: set[tuple[str | None, str]]) -> bool:
    if not resume_entries:
        return False
    key = (job.recording_id, job.chunk_id)
    if key in resume_entries:
        return True
    if (None, job.chunk_id) in resume_entries:
        return True
    return False


def _render_sockeye_script(
    dataset: Path,
    plans: Sequence[infer_orchestrator.InferPlan],
    *,
    job_name: str,
    account: str | None,
    partition: str | None,
    gres: str | None,
    time_limit: str | None,
    cpus_per_task: int | None,
    mem: str | None,
    resume_completed: bool,
) -> str:
    dataset = dataset.expanduser().resolve()
    first_plan = plans[0]

    def _relative(path: Path) -> str:
        try:
            return str(Path(path).resolve().relative_to(dataset))
        except ValueError:
            return str(Path(path).resolve())

    manifest_entries = [f'  "{_relative(plan.manifest_path)}"' for plan in plans]
    output_entries = [f'  "{_relative(plan.recording_output)}"' for plan in plans]
    telemetry_entries = [f'  "{_relative(plan.telemetry_log)}"' for plan in plans]
    resume_entries = []
    if resume_completed:
        resume_entries = [
            f'  "{_relative(_telemetry_summary_path(plan.telemetry_log))}"' for plan in plans
        ]

    lines = ["#!/bin/bash", f"#SBATCH --job-name={job_name}"]
    if account:
        lines.append(f"#SBATCH --account={account}")
    if partition:
        lines.append(f"#SBATCH --partition={partition}")
    if gres:
        lines.append(f"#SBATCH --gres={gres}")
    if time_limit:
        lines.append(f"#SBATCH --time={time_limit}")
    if cpus_per_task:
        lines.append(f"#SBATCH --cpus-per-task={cpus_per_task}")
    if mem:
        lines.append(f"#SBATCH --mem={mem}")
    lines.append(f"#SBATCH --array=1-{len(plans)}")
    lines.append("")
    lines.append("set -euo pipefail")
    lines.append(f'DATASET="{dataset}"')
    lines.append("MANIFESTS=(")
    lines.extend(manifest_entries)
    lines.append(")")
    lines.append("OUTPUTS=(")
    lines.extend(output_entries)
    lines.append(")")
    lines.append("TELEMETRY=(")
    lines.extend(telemetry_entries)
    lines.append(")")
    if resume_completed:
        lines.append("RESUMES=(")
        lines.extend(resume_entries)
        lines.append(")")
    lines.extend(
        [
            "IDX=$(($SLURM_ARRAY_TASK_ID-1))",
            "MANIFEST=${MANIFESTS[$IDX]}",
            "OUTPUT=${OUTPUTS[$IDX]}",
            "TELEMETRY_LOG=${TELEMETRY[$IDX]}",
        ]
    )
    if resume_completed:
        lines.append("RESUME_SUMMARY=${RESUMES[$IDX]}")
    lines.extend(
        [
            'cd "$DATASET"',
        ]
    )
    command = [
        "badc",
        "infer",
        "run",
        '"$MANIFEST"',
        "--output-dir",
        '"$OUTPUT"',
        "--telemetry-log",
        '"$TELEMETRY_LOG"',
    ]
    if first_plan.max_gpus is not None:
        command += ["--max-gpus", str(first_plan.max_gpus)]
    if first_plan.cpu_workers > 0:
        command += ["--cpu-workers", str(first_plan.cpu_workers)]
    if first_plan.use_hawkears:
        command.append("--use-hawkears")
    for arg in first_plan.hawkears_args:
        command += ["--hawkears-arg", arg]
    lines.append("CMD=(" + " ".join(command) + ")")
    if resume_completed:
        lines.extend(
            [
                'if [ -f "$RESUME_SUMMARY" ]; then',
                '  echo "Resume summary found: $RESUME_SUMMARY"',
                '  CMD+=("--resume-summary" "$RESUME_SUMMARY")',
                "else",
                '  echo "Resume summary $RESUME_SUMMARY not found; running full manifest."',
                "fi",
            ]
        )
    lines.append("echo Running: ${CMD[*]}")
    lines.append("${CMD[@]}")
    return "\n".join(lines) + "\n"


def _prepare_job_contexts(
    jobs: Sequence[InferenceJob],
    default_output: Path,
    allow_dataset_outputs: bool,
) -> list[tuple[InferenceJob, Path, Path | None]]:
    """Build output/dataset context tuples for each inference job.

    Parameters
    ----------
    jobs : Sequence[InferenceJob]
        Jobs parsed from the manifest CSV.
    default_output : Path
        Fallback directory for inference outputs when no dataset root is detected.
    allow_dataset_outputs : bool
        When ``True``, redirects outputs into the DataLad dataset that provided the
        chunk so provenance is preserved.

    Returns
    -------
    list of tuple
        Each tuple contains the job, the resolved output directory, and the dataset
        root (``None`` when no dataset owns the chunk).
    """

    contexts: list[tuple[InferenceJob, Path, Path | None]] = []
    for job in jobs:
        dataset_root = data_utils.find_dataset_root(job.chunk_path)
        output_base = default_output
        if allow_dataset_outputs and dataset_root:
            output_base = dataset_root / DEFAULT_INFER_OUTPUT
        contexts.append((job, output_base, dataset_root))
    return contexts


def _relativize(path: Path, root: Path) -> str:
    """Return ``path`` relative to ``root`` when possible.

    Parameters
    ----------
    path : Path
        Absolute or relative path to convert.
    root : Path
        Candidate base directory.

    Returns
    -------
    str
        Relative string when ``path`` is inside ``root``; otherwise the absolute path.
    """

    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path)


def _print_datalad_run_instructions(
    *,
    manifest: Path,
    job_contexts: Sequence[tuple[InferenceJob, Path, Path | None]],
    max_gpus: int | None,
    output_dir: Path,
    runner_cmd: str | None,
    telemetry_log: Path,
    max_retries: int,
    use_hawkears: bool,
    hawkears_args: Sequence[str],
    cpu_workers: int,
    resume_summary: Path | None,
) -> None:
    """Render a ``datalad run`` command for the provided jobs.

    Parameters
    ----------
    manifest : Path
        Manifest CSV driving the inference job list. Must live inside the dataset root.
    job_contexts : Sequence[tuple[InferenceJob, Path, Path | None]]
        Job details plus the target output path and dataset root (when available).
    max_gpus : int, optional
        Maximum GPUs to encode in the generated command. ``None`` preserves
        auto-detect behavior.
    output_dir : Path
        Requested output directory from the CLI invocation.
    runner_cmd : str, optional
        Custom runner command to include in the generated invocation.
    telemetry_log : Path
        Telemetry log path to embed in the generated command.
    max_retries : int
        Retry budget to embed in the printed command.
    use_hawkears : bool
        Indicates whether ``--use-hawkears`` should be appended.
    hawkears_args : Sequence[str]
        Additional HawkEars CLI flags.
    cpu_workers : int
        Number of CPU workers to encode; relevant when no GPUs are present.
    resume_summary : Path, optional
        Scheduler summary JSON produced by a previous run; when provided the generated
        command includes ``--resume-summary`` so successful chunks are skipped.

    Raises
    ------
    typer.Exit
        When the manifest is outside the dataset root, when multiple datasets are
        involved, or when no dataset context exists (since ``datalad run`` would fail).
    """

    dataset_roots = {ctx[2] for ctx in job_contexts if ctx[2] is not None}
    dataset_roots.discard(None)
    if not dataset_roots:
        console.print(
            "Chunks are not located inside a DataLad dataset; cannot emit datalad run command.",
            style="red",
        )
        raise typer.Exit(code=1) from None
    if len(dataset_roots) > 1:
        console.print(
            "Chunks span multiple DataLad datasets; run them per-dataset or specify --output-dir.",
            style="red",
        )
        raise typer.Exit(code=1) from None
    dataset_root = dataset_roots.pop()
    try:
        manifest_rel = manifest.resolve().relative_to(dataset_root.resolve())
    except ValueError:
        console.print(
            f"Manifest {manifest} is outside dataset root {dataset_root}; move it inside before using datalad run.",
            style="red",
        )
        raise typer.Exit(code=1) from None
    output_rel = _relativize(job_contexts[0][1], dataset_root)
    cmd: list[str] = ["badc", "infer", "run", str(manifest_rel)]
    if max_gpus is not None:
        cmd += ["--max-gpus", str(max_gpus)]
    if output_dir != DEFAULT_INFER_OUTPUT:
        cmd += ["--output-dir", _relativize(output_dir, dataset_root)]
    if runner_cmd:
        cmd += ["--runner-cmd", runner_cmd]
    if max_retries != 2:
        cmd += ["--max-retries", str(max_retries)]
    rel_telemetry = _relativize(telemetry_log, dataset_root)
    cmd += ["--telemetry-log", rel_telemetry]
    if use_hawkears:
        cmd.append("--use-hawkears")
    for arg in hawkears_args:
        cmd += ["--hawkears-arg", arg]
    if cpu_workers > 0:
        cmd += ["--cpu-workers", str(cpu_workers)]
    if resume_summary:
        cmd += ["--resume-summary", _relativize(resume_summary, dataset_root)]
    datalad_cmd = [
        "datalad",
        "run",
        "-m",
        f"badc infer {manifest.name}",
        "--input",
        str(manifest_rel),
        "--output",
        output_rel,
        "--",
    ] + cmd
    console.print(
        f"Run the following from the dataset root ({dataset_root}) to capture provenance:",
        style="bold",
    )
    console.print(f"  {shlex.join(datalad_cmd)}")


def _format_metrics(entry: dict | None) -> str:
    if not entry:
        return "-"
    parts = []
    util = entry.get("utilization")
    if util is not None:
        parts.append(f"{util}%")
    used = entry.get("memory_used_mb")
    total = entry.get("memory_total_mb")
    if used is not None:
        if total:
            parts.append(f"{used}/{total} MiB")
        else:
            parts.append(f"{used} MiB")
    return " ".join(parts) if parts else "-"


def _sparkline(
    values: Sequence[float],
    *,
    width: int = 12,
    palette: str = " .:-=+*#%@",
) -> str:
    """Return an ASCII sparkline for ``values``."""

    if not values:
        return "-"
    if width < 1:
        width = 1
    if len(values) > width:
        step = len(values) / width
        sampled = [values[int(i * step)] for i in range(width)]
    else:
        sampled = list(values)
    v_min = min(sampled)
    v_max = max(sampled)
    if v_max == v_min:
        idx = max(0, min(len(palette) - 1, len(palette) // 2))
        return palette[idx] * len(sampled)
    out = []
    span = v_max - v_min
    for value in sampled:
        norm = (value - v_min) / span
        idx = min(len(palette) - 1, max(0, int(norm * (len(palette) - 1))))
        out.append(palette[idx])
    return "".join(out)


def _write_csv(rows: Sequence[Sequence[object]], headers: Sequence[str], out_path: Path) -> None:
    """Write ``rows`` to ``out_path`` with ``headers``."""

    out_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [",".join(headers)]
    for row in rows:
        formatted = ["" if value is None else str(value) for value in row]
        lines.append(",".join(formatted))
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _select_metric_entry(details: dict | None) -> dict | None:
    """Return the preferred GPU metric block for a telemetry record."""

    if not isinstance(details, dict):
        return None
    gpu_metrics = details.get("gpu_metrics")
    if not isinstance(gpu_metrics, dict):
        return None
    after = gpu_metrics.get("after")
    if isinstance(after, dict):
        return after
    before = gpu_metrics.get("before")
    if isinstance(before, dict):
        return before
    return None


def _extract_attempt(details: dict | None) -> int | None:
    """Return the attempt counter embedded in telemetry details (if any)."""

    if not isinstance(details, dict):
        return None
    attempt = details.get("attempt")
    if isinstance(attempt, (int, float)):
        return int(attempt)
    return None


def _summarize_gpu_stats(records: list[TelemetryRecord]) -> dict[str, dict]:
    """Aggregate telemetry entries per GPU for dashboard display."""

    trend_window = 24
    summaries: dict[str, dict] = defaultdict(
        lambda: {
            "name": None,
            "events": 0,
            "success": 0,
            "failures": 0,
            "runtime_sum": 0.0,
            "runtime_samples": 0,
            "util_samples": [],
            "memory_samples": [],
            "memory_total": None,
            "retry_attempts": 0,
            "retry_events": 0,
            "failure_attempts": 0,
            "last_status": "-",
            "last_chunk": "-",
            "last_timestamp": "-",
            "last_metrics": None,
            "util_history": [],
            "memory_history": [],
            "retry_history": [],
        }
    )
    for rec in records:
        key = f"GPU {rec.gpu_index}" if rec.gpu_index is not None else "CPU"
        summary = summaries[key]
        summary["name"] = rec.gpu_name or summary["name"] or key
        summary["events"] += 1
        attempt_value = _extract_attempt(rec.details)
        event_attempt = max(attempt_value or 1, 1)
        event_retries = max(event_attempt - 1, 0)
        if rec.status.lower() == "success":
            summary["success"] += 1
            if event_retries:
                summary["retry_attempts"] += event_retries
                summary["retry_events"] += 1
        elif rec.status.lower() == "failure":
            summary["failures"] += 1
            summary["failure_attempts"] += event_attempt
        if rec.runtime_s is not None:
            summary["runtime_sum"] += rec.runtime_s
            summary["runtime_samples"] += 1
        metric_entry = _select_metric_entry(rec.details)
        if metric_entry:
            summary["last_metrics"] = metric_entry
            util = metric_entry.get("utilization")
            if isinstance(util, (int, float)):
                summary["util_samples"].append(float(util))
                summary["util_history"].append(float(util))
            mem_used = metric_entry.get("memory_used_mb")
            if isinstance(mem_used, (int, float)):
                summary["memory_samples"].append(float(mem_used))
                summary["memory_history"].append(float(mem_used))
            mem_total = metric_entry.get("memory_total_mb")
            if isinstance(mem_total, (int, float)):
                summary["memory_total"] = int(mem_total)
        summary["last_status"] = rec.status
        summary["last_chunk"] = rec.chunk_id
        summary["last_timestamp"] = rec.timestamp or summary["last_timestamp"]
        summary["retry_history"].append(event_retries)
    finalized: dict[str, dict] = {}
    for key, data in summaries.items():
        avg_runtime = (
            data["runtime_sum"] / data["runtime_samples"] if data["runtime_samples"] else None
        )
        util_samples = data["util_samples"]
        if util_samples:
            util_stats = {
                "min": min(util_samples),
                "avg": sum(util_samples) / len(util_samples),
                "max": max(util_samples),
            }
        else:
            util_stats = None
        mem_samples = data["memory_samples"]
        max_memory = max(mem_samples) if mem_samples else None
        finalized[key] = {
            "name": data["name"] or key,
            "events": data["events"],
            "success": data["success"],
            "failures": data["failures"],
            "retry_attempts": data["retry_attempts"],
            "retry_events": data["retry_events"],
            "failure_attempts": data["failure_attempts"],
            "avg_runtime": avg_runtime,
            "util_stats": util_stats,
            "max_memory": max_memory,
            "memory_total": data["memory_total"],
            "last_status": data["last_status"],
            "last_chunk": data["last_chunk"],
            "last_timestamp": data["last_timestamp"],
            "last_metrics": data["last_metrics"],
            "util_history": data["util_history"][-trend_window:],
            "memory_history": data["memory_history"][-trend_window:],
            "retry_history": data["retry_history"][-trend_window:],
        }
    return finalized


def _build_monitor_renderable(records: list, tail: int) -> Group | Panel:
    if not records:
        return Panel("No telemetry entries found.", title="Telemetry")
    summary = _summarize_gpu_stats(records)
    gpu_table = Table(title="GPU Utilization", expand=True)
    gpu_table.add_column("GPU")
    gpu_table.add_column("Events", justify="right")
    gpu_table.add_column("Success", justify="right")
    gpu_table.add_column("Fail", justify="right")
    gpu_table.add_column("Retry attempts", justify="right")
    gpu_table.add_column("Failed attempts", justify="right")
    gpu_table.add_column("Avg Runtime (s)", justify="right")
    gpu_table.add_column("Util% (min/avg/max)", justify="right")
    gpu_table.add_column("VRAM max (MiB)", justify="right")
    gpu_table.add_column("Util trend")
    gpu_table.add_column("VRAM trend (MiB)")
    gpu_table.add_column("Retry trend")
    gpu_table.add_column("Last Status")
    gpu_table.add_column("Last Chunk")
    gpu_table.add_column("Updated")
    for gpu_name in sorted(summary):
        entry = summary[gpu_name]
        label = gpu_name
        if entry["name"] and entry["name"] != gpu_name:
            label = f"{gpu_name} — {entry['name']}"
        avg_runtime = entry["avg_runtime"]
        runtime_display = f"{avg_runtime:.1f}" if avg_runtime is not None else "-"
        util_stats = entry["util_stats"]
        if util_stats:
            util_display = (
                f"{util_stats['min']:.0f}/{util_stats['avg']:.0f}/{util_stats['max']:.0f}"
            )
        else:
            util_display = "-"
        if entry["max_memory"] is not None:
            if entry["memory_total"]:
                mem_display = f"{entry['max_memory']:.0f}/{entry['memory_total']} "
            else:
                mem_display = f"{entry['max_memory']:.0f} "
            mem_display += "MiB"
        else:
            mem_display = "-"
        util_trend = _sparkline(entry.get("util_history") or [], width=10)
        mem_trend = _sparkline(entry.get("memory_history") or [], width=10)
        retry_trend = _sparkline(entry.get("retry_history") or [], width=10)
        gpu_table.add_row(
            label,
            str(entry["events"]),
            str(entry["success"]),
            str(entry["failures"]),
            str(entry["retry_attempts"]),
            str(entry["failure_attempts"]),
            runtime_display,
            util_display,
            mem_display,
            util_trend,
            mem_trend,
            retry_trend,
            entry["last_status"],
            entry["last_chunk"],
            entry["last_timestamp"] or "-",
        )
    tail_table = Table(title=f"Last {tail} Events", expand=True)
    tail_table.add_column("Time")
    tail_table.add_column("Status")
    tail_table.add_column("Chunk")
    tail_table.add_column("GPU")
    tail_table.add_column("Runtime (s)")
    tail_table.add_column("Attempt")
    tail_table.add_column("Metrics")
    for rec in records[-tail:]:
        attempt = _extract_attempt(rec.details)
        tail_table.add_row(
            rec.timestamp,
            rec.status,
            rec.chunk_id,
            f"{rec.gpu_index}" if rec.gpu_index is not None else "CPU",
            "-" if rec.runtime_s is None else f"{rec.runtime_s:.1f}",
            "-" if attempt is None else str(attempt),
            _format_metrics(_select_metric_entry(rec.details)),
        )
    return Group(gpu_table, tail_table)


@infer_app.command("aggregate")
def infer_aggregate(
    detections_dir: Annotated[
        Path,
        typer.Argument(help="Directory containing inference outputs (JSON)."),
    ],
    output: Annotated[
        Path,
        typer.Option("--output", help="Summary CSV path."),
    ] = Path("artifacts/aggregate/summary.csv"),
    manifest: Annotated[
        Optional[Path],
        typer.Option(
            "--manifest",
            help="Optional chunk manifest CSV to enrich metadata.",
            exists=True,
            dir_okay=False,
            file_okay=True,
            resolve_path=True,
        ),
    ] = None,
    parquet: Annotated[
        Optional[Path],
        typer.Option("--parquet", help="Optional Parquet output path (requires duckdb)."),
    ] = None,
) -> None:
    """Aggregate per-chunk detection JSON files into a summary CSV.

    Parameters
    ----------
    detections_dir : Path
        Directory holding JSON outputs from ``badc infer run``.
    output : Path
        Destination CSV path for the aggregated summary.
    """

    from badc.aggregate import load_detections, write_parquet, write_summary_csv

    records = load_detections(detections_dir, manifest=manifest)
    if not records:
        console.print("No detections found.", style="yellow")
        return
    summary_path = write_summary_csv(records, output)
    console.print(f"Wrote detection summary to {summary_path}")
    if parquet:
        try:
            parquet_path = write_parquet(records, parquet)
        except RuntimeError as exc:
            console.print(str(exc), style="red")
        else:
            console.print(f"Wrote Parquet export to {parquet_path}")


@infer_app.command("monitor")
def infer_monitor(
    log_path: Annotated[
        Path,
        typer.Option("--log", help="Telemetry log path to inspect."),
    ] = Path("data/telemetry/infer/log.jsonl"),
    tail: Annotated[
        int,
        typer.Option("--tail", help="Number of recent events to display."),
    ] = 15,
    follow: Annotated[
        bool,
        typer.Option("--follow/--once", help="Continuously refresh the view."),
    ] = False,
    interval: Annotated[
        float,
        typer.Option("--interval", help="Refresh interval in seconds when following."),
    ] = 5.0,
) -> None:
    """Render GPU/telemetry summaries for a run-specific log."""

    def render() -> Group | Panel:
        records = load_telemetry(log_path)
        return _build_monitor_renderable(records, tail)

    if follow:
        console.print(f"Monitoring {log_path} (Ctrl+C to stop)...", style="bold")
        try:
            refresh = max(1, int(1 / max(interval, 0.1)))
            with Live(render(), refresh_per_second=refresh) as live:
                while True:
                    time.sleep(interval)
                    live.update(render())
        except KeyboardInterrupt:
            console.print("\nStopped monitor.", style="yellow")
    else:
        console.print(render())


@report_app.command("summary")
def report_summary(
    parquet: Annotated[
        Path,
        typer.Option("--parquet", help="Parquet detections file", exists=True, dir_okay=False),
    ],
    group_by: Annotated[
        str,
        typer.Option(
            "--group-by",
            help="Comma-separated columns to group by (label, recording_id)",
        ),
    ] = "label",
    output: Annotated[
        Optional[Path],
        typer.Option("--output", help="Optional CSV path for the summary."),
    ] = None,
    limit: Annotated[
        int,
        typer.Option("--limit", help="Rows to display in console."),
    ] = 20,
) -> None:
    """Summarize detections via DuckDB (group counts + avg confidence)."""

    from badc.aggregate import summarize_parquet

    groups = [col.strip() for col in group_by.split(",") if col.strip()]
    try:
        rows = summarize_parquet(parquet, group_by=groups)
    except (RuntimeError, ValueError) as exc:
        console.print(str(exc), style="red")
        raise typer.Exit(code=1) from exc
    if not rows:
        console.print("No detections available in the Parquet file.", style="yellow")
        return
    headers = groups + ["detections", "avg_confidence"]
    table = Table(title="Detection summary", expand=True)
    for header in headers:
        table.add_column(header)
    for row in rows[:limit]:
        formatted = [str(value) if value is not None else "" for value in row]
        if len(formatted) == len(headers):
            table.add_row(*formatted)
    console.print(table)
    if output:
        lines = [",".join(headers)]
        for row in rows:
            line = ",".join("" if value is None else str(value) for value in row)
            lines.append(line)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text("\n".join(lines) + "\n")
        console.print(f"Wrote summary CSV to {output}")


@report_app.command("quicklook")
def report_quicklook(
    parquet: Annotated[
        Path,
        typer.Option("--parquet", help="Parquet detections file", exists=True, dir_okay=False),
    ],
    top_labels: Annotated[
        int,
        typer.Option(
            "--top-labels",
            help="Number of label rows to display.",
        ),
    ] = 10,
    top_recordings: Annotated[
        int,
        typer.Option(
            "--top-recordings",
            help="Number of recording rows to display.",
        ),
    ] = 5,
    output_dir: Annotated[
        Optional[Path],
        typer.Option(
            "--output-dir",
            help="Optional directory for CSV exports (labels.csv, recordings.csv, chunks.csv).",
        ),
    ] = None,
) -> None:
    """Generate quicklook tables/plots for canonical detections."""

    from badc.aggregate import quicklook_metrics

    try:
        quicklook = quicklook_metrics(
            parquet,
            top_labels=top_labels,
            top_recordings=top_recordings,
        )
    except RuntimeError as exc:
        console.print(str(exc), style="red")
        raise typer.Exit(code=1) from exc

    if not quicklook.top_labels:
        console.print("No detections found in the Parquet file.", style="yellow")
        return

    label_table = Table(title=f"Top {top_labels} labels", expand=True)
    label_table.add_column("Label")
    label_table.add_column("Name")
    label_table.add_column("Detections", justify="right")
    label_table.add_column("Avg confidence", justify="right")
    for label, label_name, detections, avg_conf in quicklook.top_labels:
        label_table.add_row(
            label,
            label_name or "",
            str(detections),
            "-" if avg_conf is None else f"{avg_conf:.3f}",
        )
    console.print(label_table)

    recording_table = Table(title=f"Top {top_recordings} recordings", expand=True)
    recording_table.add_column("Recording")
    recording_table.add_column("Detections", justify="right")
    recording_table.add_column("Avg confidence", justify="right")
    for recording_id, detections, avg_conf in quicklook.top_recordings:
        recording_table.add_row(
            recording_id or "unknown",
            str(detections),
            "-" if avg_conf is None else f"{avg_conf:.3f}",
        )
    console.print(recording_table)

    if quicklook.chunk_timeline:
        counts = [float(row[2]) for row in quicklook.chunk_timeline]
        timeline = _sparkline(counts, width=min(60, len(counts)))
        first_chunk = quicklook.chunk_timeline[0][0]
        last_chunk = quicklook.chunk_timeline[-1][0]
        chunk_table = Table(title="Chunk detections (chronological)", expand=True)
        chunk_table.add_column("Chunk")
        chunk_table.add_column("Start (s)", justify="right")
        chunk_table.add_column("Detections", justify="right")
        chunk_table.add_column("Avg confidence", justify="right")
        for chunk_id, start_ms, det_count, avg_conf in quicklook.chunk_timeline[:10]:
            start_display = "-" if start_ms is None else f"{start_ms / 1000:.1f}"
            chunk_table.add_row(
                chunk_id,
                start_display,
                str(det_count),
                "-" if avg_conf is None else f"{avg_conf:.3f}",
            )
        console.print(chunk_table)
        console.print("Chunk timeline (detections per chunk):", style="bold")
        console.print(f"  {timeline}")
        console.print(
            f"  first chunk: {first_chunk}, last chunk: {last_chunk}, total chunks: {len(quicklook.chunk_timeline)}"
        )

    if output_dir:
        output_dir.mkdir(parents=True, exist_ok=True)
        _write_csv(
            quicklook.top_labels,
            ["label", "label_name", "detections", "avg_confidence"],
            output_dir / "labels.csv",
        )
        _write_csv(
            quicklook.top_recordings,
            ["recording_id", "detections", "avg_confidence"],
            output_dir / "recordings.csv",
        )
        _write_csv(
            quicklook.chunk_timeline,
            ["chunk_id", "chunk_start_ms", "detections", "avg_confidence"],
            output_dir / "chunks.csv",
        )
        console.print(f"Wrote quicklook CSVs to {output_dir}")


@report_app.command("parquet")
def report_parquet(
    parquet: Annotated[
        Path,
        typer.Option(
            "--parquet", help="Canonical detections Parquet file.", exists=True, dir_okay=False
        ),
    ],
    top_labels: Annotated[
        int,
        typer.Option("--top-labels", help="Number of label rows to display."),
    ] = 20,
    top_recordings: Annotated[
        int,
        typer.Option("--top-recordings", help="Number of recording rows to display."),
    ] = 10,
    bucket_minutes: Annotated[
        int,
        typer.Option("--bucket-minutes", help="Bucket size (minutes) for the timeline."),
    ] = 60,
    output_dir: Annotated[
        Path | None,
        typer.Option("--output-dir", help="Optional directory for CSV/JSON exports."),
    ] = None,
) -> None:
    """Summarize canonical detections via DuckDB with optional exports."""

    from badc.aggregate import parquet_report

    try:
        report = parquet_report(
            parquet,
            top_labels=top_labels,
            top_recordings=top_recordings,
            bucket_minutes=bucket_minutes,
        )
    except RuntimeError as exc:
        console.print(str(exc), style="red")
        raise typer.Exit(code=1) from exc
    summary_table = Table(title="Detection summary", expand=True)
    summary_table.add_column("Metric")
    summary_table.add_column("Value", justify="right")
    for key, value in report.summary.items():
        summary_table.add_row(key.replace("_", " ").title(), "-" if value is None else str(value))
    console.print(summary_table)

    label_table = Table(title="Top labels", expand=True)
    label_table.add_column("Label")
    label_table.add_column("Name")
    label_table.add_column("Detections", justify="right")
    label_table.add_column("Avg conf", justify="right")
    for label, name, detections, avg_conf in report.labels:
        label_table.add_row(
            label,
            name or "",
            str(detections),
            "-" if avg_conf is None else f"{avg_conf:.3f}",
        )
    console.print(label_table)

    recording_table = Table(title="Top recordings", expand=True)
    recording_table.add_column("Recording")
    recording_table.add_column("Detections", justify="right")
    recording_table.add_column("Avg conf", justify="right")
    for recording_id, detections, avg_conf in report.recordings:
        recording_table.add_row(
            recording_id,
            str(detections),
            "-" if avg_conf is None else f"{avg_conf:.3f}",
        )
    console.print(recording_table)

    timeline_table = Table(title=f"Timeline (bucket={bucket_minutes}m)", expand=True)
    timeline_table.add_column("Bucket")
    timeline_table.add_column("Start (ms)", justify="right")
    timeline_table.add_column("Detections", justify="right")
    timeline_table.add_column("Avg conf", justify="right")
    for bucket, start_ms, detections, avg_conf in report.timeline:
        timeline_table.add_row(
            bucket,
            "-" if start_ms is None else str(start_ms),
            str(detections),
            "-" if avg_conf is None else f"{avg_conf:.3f}",
        )
    console.print(timeline_table)

    if output_dir:
        output_dir.mkdir(parents=True, exist_ok=True)
        _write_csv(
            report.labels,
            ["label", "label_name", "detections", "avg_confidence"],
            output_dir / "labels.csv",
        )
        _write_csv(
            report.recordings,
            ["recording_id", "detections", "avg_confidence"],
            output_dir / "recordings.csv",
        )
        _write_csv(
            report.timeline,
            ["bucket", "bucket_start_ms", "detections", "avg_confidence"],
            output_dir / "timeline.csv",
        )
        summary_path = output_dir / "summary.json"
        summary_path.write_text(json.dumps(report.summary, indent=2), encoding="utf-8")
        console.print(f"Wrote parquet report artifacts to {output_dir}")


@report_app.command("duckdb")
def report_duckdb(
    parquet: Annotated[
        Path,
        typer.Option(
            "--parquet", help="Canonical detections Parquet file.", exists=True, dir_okay=False
        ),
    ],
    database: Annotated[
        Path,
        typer.Option("--database", help="DuckDB database to create or update."),
    ] = Path("artifacts/aggregate/detections.duckdb"),
    bucket_minutes: Annotated[
        int,
        typer.Option("--bucket-minutes", help="Bucket size (minutes) for the timeline view."),
    ] = 60,
    top_labels: Annotated[
        int,
        typer.Option("--top-labels", help="Number of label rows to display."),
    ] = 15,
    top_recordings: Annotated[
        int,
        typer.Option("--top-recordings", help="Number of recording rows to display."),
    ] = 10,
    export_dir: Annotated[
        Path | None,
        typer.Option(
            "--export-dir",
            help="Optional directory for CSV exports (label_summary.csv, recording_summary.csv, timeline.csv).",
        ),
    ] = None,
) -> None:
    """Materialize detections into DuckDB and print ready-to-review summaries."""

    try:
        import duckdb  # type: ignore
    except ModuleNotFoundError as exc:  # pragma: no cover - optional dependency
        console.print(
            "duckdb is required for this command. Install with `pip install duckdb`.", style="red"
        )
        raise typer.Exit(code=1) from exc

    bucket_minutes = max(1, bucket_minutes)
    bucket_ms = bucket_minutes * 60 * 1000
    database = database.expanduser()
    database.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(database))
    console.print(f"Loading detections into DuckDB: {database}", style="bold")
    con.execute(
        "CREATE OR REPLACE TABLE detections AS SELECT * FROM read_parquet(?)", [str(parquet)]
    )
    con.execute(
        """
        CREATE OR REPLACE VIEW label_summary AS
        SELECT label,
               COALESCE(label_name, '') AS label_name,
               COUNT(*) AS detections,
               AVG(confidence) AS avg_confidence
        FROM detections
        GROUP BY label, label_name
        ORDER BY detections DESC
        """
    )
    con.execute(
        """
        CREATE OR REPLACE VIEW recording_summary AS
        SELECT recording_id,
               COUNT(*) AS detections,
               AVG(confidence) AS avg_confidence
        FROM detections
        GROUP BY recording_id
        ORDER BY detections DESC
        """
    )
    con.execute(
        f"""
        CREATE OR REPLACE VIEW timeline_summary AS
        WITH chunk_data AS (
            SELECT chunk_id,
                   COALESCE(chunk_start_ms, 0) AS chunk_start_ms,
                   CAST(FLOOR(COALESCE(chunk_start_ms, 0) / {bucket_ms}) AS BIGINT) AS bucket_index,
                   COUNT(*) AS detections,
                   AVG(confidence) AS avg_confidence
            FROM detections
            GROUP BY chunk_id, chunk_start_ms, bucket_index
        )
        SELECT bucket_index,
               MIN(chunk_start_ms) AS bucket_start_ms,
               SUM(detections) AS detections,
               AVG(avg_confidence) AS avg_confidence
        FROM chunk_data
        GROUP BY bucket_index
        ORDER BY bucket_start_ms, bucket_index
        """
    )
    summary = con.execute(
        """
        SELECT COUNT(*) AS detections,
               COUNT(DISTINCT label) AS label_count,
               COUNT(DISTINCT recording_id) AS recording_count,
               MIN(chunk_start_ms) AS first_chunk_ms,
               MAX(chunk_start_ms) AS last_chunk_ms
        FROM detections
        """
    ).fetchone()
    label_rows = con.execute(
        "SELECT label, label_name, detections, avg_confidence FROM label_summary LIMIT ?",
        [max(1, top_labels)],
    ).fetchall()
    recording_rows = con.execute(
        "SELECT recording_id, detections, avg_confidence FROM recording_summary LIMIT ?",
        [max(1, top_recordings)],
    ).fetchall()
    timeline_rows = con.execute(
        "SELECT bucket_index, bucket_start_ms, detections, avg_confidence FROM timeline_summary"
    ).fetchall()
    con.close()

    summary_table = Table(title="DuckDB summary", expand=True)
    summary_table.add_column("Metric")
    summary_table.add_column("Value", justify="right")
    metrics = [
        ("Detections", summary[0]),
        ("Unique labels", summary[1]),
        ("Recordings", summary[2]),
        ("First chunk (ms)", summary[3]),
        ("Last chunk (ms)", summary[4]),
    ]
    for label, value in metrics:
        summary_table.add_row(label, "-" if value is None else str(value))
    console.print(summary_table)

    label_table = Table(title=f"Top {top_labels} labels", expand=True)
    label_table.add_column("Label")
    label_table.add_column("Name")
    label_table.add_column("Detections", justify="right")
    label_table.add_column("Avg confidence", justify="right")
    for row in label_rows:
        label_table.add_row(
            row[0] or "unknown",
            row[1] or "",
            str(int(row[2] or 0)),
            "-" if row[3] is None else f"{row[3]:.3f}",
        )
    console.print(label_table)

    recording_table = Table(title=f"Top {top_recordings} recordings", expand=True)
    recording_table.add_column("Recording")
    recording_table.add_column("Detections", justify="right")
    recording_table.add_column("Avg confidence", justify="right")
    for row in recording_rows:
        recording_table.add_row(
            row[0] or "unknown",
            str(int(row[1] or 0)),
            "-" if row[2] is None else f"{row[2]:.3f}",
        )
    console.print(recording_table)

    if timeline_rows:
        timeline_table = Table(title="Timeline buckets", expand=True)
        timeline_table.add_column("Bucket")
        timeline_table.add_column("Start (ms)", justify="right")
        timeline_table.add_column("Detections", justify="right")
        timeline_table.add_column("Avg confidence", justify="right")
        for bucket_index, start_ms, det_count, avg_conf in timeline_rows[:20]:
            timeline_table.add_row(
                str(bucket_index),
                "-" if start_ms is None else str(int(start_ms)),
                str(int(det_count or 0)),
                "-" if avg_conf is None else f"{avg_conf:.3f}",
            )
        console.print(timeline_table)
        counts = [float(row[2]) for row in timeline_rows]
        sparkline = _sparkline(counts, width=min(80, len(counts)))
        console.print(
            f"Timeline sparkline ({bucket_minutes}-minute buckets): {sparkline}", style="bold"
        )

    if export_dir:
        export_dir.mkdir(parents=True, exist_ok=True)
        _write_csv(
            label_rows,
            ["label", "label_name", "detections", "avg_confidence"],
            export_dir / "label_summary.csv",
        )
        _write_csv(
            recording_rows,
            ["recording_id", "detections", "avg_confidence"],
            export_dir / "recording_summary.csv",
        )
        _write_csv(
            timeline_rows,
            ["bucket_index", "bucket_start_ms", "detections", "avg_confidence"],
            export_dir / "timeline.csv",
        )
        console.print(f"Wrote DuckDB CSV exports to {export_dir}")

    console.print(
        f"DuckDB database ready at {database}. Run `duckdb {database}` for ad-hoc queries.",
        style="green",
    )


@report_app.command("bundle")
def report_bundle(
    parquet: Annotated[
        Path,
        typer.Option(
            "--parquet", help="Canonical detections Parquet file.", exists=True, dir_okay=False
        ),
    ],
    output_dir: Annotated[
        Path | None,
        typer.Option(
            "--output-dir",
            help="Base directory for generated artifacts (defaults to the Parquet parent).",
        ),
    ] = None,
    run_prefix: Annotated[
        str | None,
        typer.Option(
            "--run-prefix",
            help="Prefix used for derived directories (defaults to the Parquet stem).",
        ),
    ] = None,
    bucket_minutes: Annotated[
        int,
        typer.Option(
            "--bucket-minutes",
            help="Bucket size (minutes) for the parquet/duckdb timeline aggregations.",
        ),
    ] = 60,
    parquet_top_labels: Annotated[
        int,
        typer.Option("--parquet-top-labels", help="Rows to show in the parquet report tables."),
    ] = 20,
    parquet_top_recordings: Annotated[
        int,
        typer.Option(
            "--parquet-top-recordings",
            help="Recording rows to show in the parquet report tables.",
        ),
    ] = 10,
    quicklook_top_labels: Annotated[
        int,
        typer.Option("--quicklook-top-labels", help="Label rows for the quicklook view."),
    ] = 10,
    quicklook_top_recordings: Annotated[
        int,
        typer.Option("--quicklook-top-recordings", help="Recording rows for the quicklook view."),
    ] = 5,
    duckdb_top_labels: Annotated[
        int,
        typer.Option("--duckdb-top-labels", help="Rows to display from duckdb.label_summary."),
    ] = 15,
    duckdb_top_recordings: Annotated[
        int,
        typer.Option(
            "--duckdb-top-recordings",
            help="Rows to display from duckdb.recording_summary.",
        ),
    ] = 10,
    quicklook: Annotated[
        bool,
        typer.Option("--quicklook/--no-quicklook", help="Generate the quicklook CSV bundle."),
    ] = True,
    parquet_report: Annotated[
        bool,
        typer.Option(
            "--parquet-report/--no-parquet-report",
            help="Generate the parquet report (CSV + summary JSON).",
        ),
    ] = True,
    duckdb_report: Annotated[
        bool,
        typer.Option(
            "--duckdb-report/--no-duckdb-report",
            help="Materialize the DuckDB database and CSV exports.",
        ),
    ] = True,
    quicklook_dir: Annotated[
        Path | None,
        typer.Option("--quicklook-dir", help="Override directory for quicklook CSVs."),
    ] = None,
    parquet_report_dir: Annotated[
        Path | None,
        typer.Option("--parquet-report-dir", help="Override directory for parquet report exports."),
    ] = None,
    duckdb_database: Annotated[
        Path | None,
        typer.Option("--duckdb-database", help="Override DuckDB database path."),
    ] = None,
    duckdb_export_dir: Annotated[
        Path | None,
        typer.Option("--duckdb-export-dir", help="Override directory for DuckDB CSV exports."),
    ] = None,
) -> None:
    """Produce quicklook, parquet, and DuckDB artifacts in one pass."""

    parquet = parquet.expanduser()
    base_dir = (output_dir or parquet.parent).expanduser()
    prefix = run_prefix or parquet.stem
    default_quicklook_dir = (base_dir / f"{prefix}_quicklook").expanduser()
    default_parquet_dir = (base_dir / f"{prefix}_parquet_report").expanduser()
    default_duckdb_path = (base_dir / f"{prefix}.duckdb").expanduser()
    default_duckdb_exports = (base_dir / f"{prefix}_duckdb_exports").expanduser()
    quicklook_dest = (quicklook_dir or default_quicklook_dir).expanduser()
    parquet_dest = (parquet_report_dir or default_parquet_dir).expanduser()
    duckdb_path = (duckdb_database or default_duckdb_path).expanduser()
    duckdb_exports = (duckdb_export_dir or default_duckdb_exports).expanduser()

    console.print(
        f"Generating aggregation bundle for {parquet} (base directory: {base_dir})", style="bold"
    )

    if quicklook:
        console.print(f"[cyan]Quicklook → {quicklook_dest}[/]")
        report_quicklook(
            parquet=parquet,
            top_labels=quicklook_top_labels,
            top_recordings=quicklook_top_recordings,
            output_dir=quicklook_dest,
        )
    else:
        console.print("Skipping quicklook bundle.", style="yellow")

    if parquet_report:
        console.print(f"[cyan]Parquet report → {parquet_dest}[/]")
        report_parquet(
            parquet=parquet,
            top_labels=parquet_top_labels,
            top_recordings=parquet_top_recordings,
            bucket_minutes=bucket_minutes,
            output_dir=parquet_dest,
        )
    else:
        console.print("Skipping parquet report.", style="yellow")

    if duckdb_report:
        console.print(f"[cyan]DuckDB report → {duckdb_path} (exports: {duckdb_exports})[/]")
        report_duckdb(
            parquet=parquet,
            database=duckdb_path,
            bucket_minutes=bucket_minutes,
            top_labels=duckdb_top_labels,
            top_recordings=duckdb_top_recordings,
            export_dir=duckdb_exports,
        )
    else:
        console.print("Skipping DuckDB materialization.", style="yellow")

    console.print("Aggregation bundle complete.", style="green")


def main() -> None:
    """Entrypoint invoked by the ``badc`` console script.

    Notes
    -----
    This thin wrapper allows ``python -m badc.cli.main`` to behave the same as the
    installed ``badc`` command, which simplifies debugging in editable installs.
    """

    app()


@app.command("telemetry")
def telemetry_monitor(
    log_path: Annotated[
        Path,
        typer.Option("--log", help="Telemetry log path."),
    ] = Path("data/telemetry/infer/log.jsonl"),
) -> None:
    """Print the most recent telemetry records for quick inspection.

    Parameters
    ----------
    log_path : Path
        JSONL file produced by :mod:`badc.telemetry` recording HawkEars runs.
    """

    records = load_telemetry(log_path)
    if not records:
        console.print("No telemetry entries found.", style="yellow")
        return
    console.print(f"Telemetry records ({len(records)}):")
    for rec in records[-10:]:
        console.print(
            f"[{rec.status}] {rec.chunk_id} (GPU {rec.gpu_index}) "
            f"{rec.timestamp} runtime={rec.runtime_s}"
        )
