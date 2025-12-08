"""Primary Typer CLI for the Bird Acoustic Data Compiler project."""

from __future__ import annotations

import queue
import shlex
import subprocess
import threading
import time
from collections import defaultdict
from pathlib import Path
from typing import Annotated, Optional, Sequence

import typer
from rich.console import Console, Group
from rich.live import Live
from rich.markup import escape
from rich.panel import Panel
from rich.table import Table

from badc import __version__, chunking
from badc import data as data_utils
from badc.audio import get_wav_duration
from badc.chunk_writer import ChunkMetadata, iter_chunk_metadata
from badc.gpu import detect_gpus
from badc.hawkears_runner import run_job
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
    file: Annotated[Path, typer.Argument(help="Path to audio file to probe.")],
    initial_duration: Annotated[
        float,
        typer.Option("--initial-duration", help="Starting chunk duration in seconds."),
    ] = 60.0,
) -> None:
    """Estimate chunk duration feasibility for a single audio file.

    Parameters
    ----------
    file : Path
        Path to the WAV file being analyzed.
    initial_duration : float
        Starting chunk size in seconds fed to the placeholder probe logic.

    Notes
    -----
    The current implementation delegates to :func:`badc.chunking.probe_chunk_duration`,
    which returns mocked values until the HawkEars-driven calibration lands.
    """

    result = chunking.probe_chunk_duration(file, initial_duration)
    console.print(
        f"Probe placeholder: max chunk {result.max_duration_s:.2f}s for {result.file}",
        style="cyan",
    )
    console.print("Notes: " + result.notes)


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
        Path,
        typer.Option("--output-dir", help="Directory for chunk files."),
    ] = Path("artifacts/chunks"),
    manifest: Annotated[
        Path,
        typer.Option("--manifest", help="Manifest CSV path."),
    ] = Path("chunk_manifest.csv"),
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
        Directory where generated chunk WAVs should be stored.
    manifest : Path
        Output manifest CSV path.
    dry_run : bool
        When ``True``, skips writing chunk files and emits mock metadata for planning.

    Notes
    -----
    Hashes are only computed when chunk files are actually written. Dry runs help plan
    output layouts without touching disk.
    """

    duration = get_wav_duration(file)
    if dry_run:
        chunk_rows = [
            ChunkMetadata(
                chunk_id=f"{file.stem}_chunk_{i}",
                path=file,
                start_ms=0,
                end_ms=0,
                overlap_ms=int(overlap * 1000),
                sha256="TODO_HASH",
            )
            for i in range(1)
        ]
    else:
        chunk_rows = list(
            iter_chunk_metadata(
                audio_path=file,
                chunk_duration_s=chunk_duration,
                overlap_s=overlap,
                output_dir=output_dir,
            )
        )
    if not chunk_rows:
        console.print("No chunks generated.", style="yellow")
        return
    manifest_path = chunking.write_manifest(
        file,
        chunk_duration,
        manifest,
        duration,
        compute_hashes=not dry_run,
        chunk_rows=chunk_rows,
    )
    console.print(
        f"Chunks {'skipped' if dry_run else f'written to {output_dir}'}; manifest at {manifest_path}"
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
            help="Number of concurrent workers when running without GPUs.",
        ),
    ] = 1,
    print_datalad_run: Annotated[
        bool,
        typer.Option(
            "--print-datalad-run",
            help="Show a ready-to-run `datalad run` command (no inference executed).",
        ),
    ] = False,
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
        Number of concurrent workers to use when no GPUs are detected.
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
    extra_args = hawkears_arg or []
    workers, detection_note = plan_workers(max_gpus=max_gpus)
    if detection_note:
        console.print(detection_note, style="yellow")
    if not jobs:
        console.print("No jobs found in manifest.", style="yellow")
        return
    if not workers:
        console.print("No GPUs detected; running without GPU affinity.", style="yellow")
        worker_pool: list[GPUWorker | None] = [None] * max(cpu_workers, 1)
    else:
        worker_pool = workers
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
        )
        return

    console.print(f"Telemetry log: {telemetry_path}")
    _run_scheduler(
        job_contexts=job_contexts,
        worker_pool=worker_pool,
        runner_cmd=runner_cmd,
        max_retries=max_retries,
        use_hawkears=use_hawkears,
        hawkears_args=extra_args,
        telemetry_path=telemetry_path,
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


def _run_scheduler(
    job_contexts: Sequence[tuple[InferenceJob, Path, Path | None]],
    worker_pool: list[GPUWorker | None],
    runner_cmd: str | None,
    max_retries: int,
    use_hawkears: bool,
    hawkears_args: Sequence[str],
    telemetry_path: Path,
) -> None:
    """Dispatch inference jobs to worker threads.

    Parameters
    ----------
    job_contexts : Sequence[tuple[InferenceJob, Path, Path | None]]
        Each tuple contains the job metadata, the output directory, and the optional
        dataset root used for provenance tracking.
    worker_pool : list[GPUWorker | None]
        GPU-bound workers (``None`` entries represent CPU-only workers).
    runner_cmd : str, optional
        Custom command to execute per chunk when ``use_hawkears`` is ``False``.
    max_retries : int
        Number of times to retry a failing job before surfacing the exception.
    use_hawkears : bool
        When ``True``, invokes the vendored HawkEars analyzer instead of the stub.
    hawkears_args : Sequence[str]
        Additional CLI arguments forwarded to HawkEars.

    Raises
    ------
    Exception
        Re-raises the first worker failure after shutting down the pool.
    """

    if not worker_pool:
        worker_pool = [None]
    job_queue: queue.Queue = queue.Queue()
    sentinel = object()
    for context in job_contexts:
        job_queue.put(context)
    for _ in worker_pool:
        job_queue.put(sentinel)

    stop_event = threading.Event()
    errors: list[Exception] = []
    runner_args = list(hawkears_args)

    def worker_loop(worker: GPUWorker | None) -> None:
        while True:
            item = job_queue.get()
            try:
                if item is sentinel:
                    return
                if stop_event.is_set():
                    continue
                job, job_output, dataset_root = item
                run_job(
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
            except Exception as exc:  # pragma: no cover - propagated to main thread
                errors.append(exc)
                stop_event.set()
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
    if cpu_workers != 1:
        cmd += ["--cpu-workers", str(cpu_workers)]
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
            "last_status": "-",
            "last_chunk": "-",
            "last_timestamp": "-",
            "last_metrics": None,
            "util_history": [],
            "memory_history": [],
        }
    )
    for rec in records:
        key = f"GPU {rec.gpu_index}" if rec.gpu_index is not None else "CPU"
        summary = summaries[key]
        summary["name"] = rec.gpu_name or summary["name"] or key
        summary["events"] += 1
        if rec.status.lower() == "success":
            summary["success"] += 1
        elif rec.status.lower() == "failure":
            summary["failures"] += 1
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
    gpu_table.add_column("Avg Runtime (s)", justify="right")
    gpu_table.add_column("Util% (min/avg/max)", justify="right")
    gpu_table.add_column("VRAM max (MiB)", justify="right")
    gpu_table.add_column("Util trend")
    gpu_table.add_column("VRAM trend (MiB)")
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
        gpu_table.add_row(
            label,
            str(entry["events"]),
            str(entry["success"]),
            str(entry["failures"]),
            runtime_display,
            util_display,
            mem_display,
            util_trend,
            mem_trend,
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
    tail_table.add_column("Metrics")
    for rec in records[-tail:]:
        tail_table.add_row(
            rec.timestamp,
            rec.status,
            rec.chunk_id,
            f"{rec.gpu_index}" if rec.gpu_index is not None else "CPU",
            "-" if rec.runtime_s is None else f"{rec.runtime_s:.1f}",
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
