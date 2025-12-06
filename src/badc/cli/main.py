"""Primary Typer CLI for the Bird Acoustic Data Cruncher project."""

from __future__ import annotations

import queue
import subprocess
import threading
from pathlib import Path
from typing import Annotated, Optional, Sequence

import typer
from rich.console import Console

from badc import __version__, chunking
from badc import data as data_utils
from badc.audio import get_wav_duration
from badc.chunk_writer import ChunkMetadata, iter_chunk_metadata
from badc.gpu import detect_gpus
from badc.hawkears_runner import run_job
from badc.infer_scheduler import GPUWorker, InferenceJob, load_jobs, plan_workers
from badc.telemetry import load_telemetry

console = Console()
app = typer.Typer(help="Utilities for chunking and processing large bird audio corpora.")
DEFAULT_DATALAD_PATH = Path("data") / "datalad"

data_app = typer.Typer(help="Manage DataLad-backed audio repositories (stub commands).")
chunk_app = typer.Typer(help="Chunking utilities and HawkEars probe helpers.")
infer_app = typer.Typer(help="Inference + aggregation helpers (placeholder).")
app.add_typer(data_app, name="data")
app.add_typer(chunk_app, name="chunk")
app.add_typer(infer_app, name="infer")


def _print_header() -> None:
    console.rule("Bird Acoustic Data Cruncher")


@app.command()
def version() -> None:
    """Show the current BADC version."""

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
    """Clone (or update) a DataLad-backed dataset and record it in the config."""

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
    """Record a dataset as disconnected and optionally remove its files."""

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
def data_status() -> None:
    """Report tracked datasets and their recorded paths/status."""

    datasets = data_utils.list_tracked_datasets()
    if not datasets:
        console.print("No datasets recorded. Run `badc data connect ...` first.")
        return

    console.print("Tracked datasets:", style="bold")
    for dataset_name in sorted(datasets):
        entry = datasets[dataset_name]
        status = entry.get("status", "unknown")
        path_display = entry.get("path", "?")
        console.print(f" - [cyan]{dataset_name}[/]: {status} ({path_display})")


@chunk_app.command("probe")
def chunk_probe(
    file: Annotated[Path, typer.Argument(help="Path to audio file to probe.")],
    initial_duration: Annotated[
        float,
        typer.Option("--initial-duration", help="Starting chunk duration in seconds."),
    ] = 60.0,
) -> None:
    """Run the placeholder chunk-size probe."""

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
    """Emit placeholder chunk IDs for the given audio file."""

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
    """Generate a chunk manifest CSV (placeholder hashing)."""

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
    """Generate chunk files (optional) and manifest."""

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
    """Display detected GPUs (index, name, VRAM)."""

    infos = detect_gpus()
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
) -> None:
    """Run HawkEars inference for each chunk listed in the manifest."""

    if runner_cmd and use_hawkears:
        raise typer.BadParameter(
            "Use either --runner-cmd or --use-hawkears, not both.", param_hint="runner"
        )

    jobs = load_jobs(manifest)
    extra_args = hawkears_arg or []
    workers = plan_workers(max_gpus=max_gpus)
    if not jobs:
        console.print("No jobs found in manifest.", style="yellow")
        return
    if not workers:
        console.print("No GPUs detected; running without GPU affinity.", style="yellow")
        worker_pool: list[GPUWorker | None] = [None] * max(cpu_workers, 1)
    else:
        worker_pool = workers
    _run_scheduler(
        jobs=jobs,
        worker_pool=worker_pool,
        output_dir=output_dir,
        runner_cmd=runner_cmd,
        max_retries=max_retries,
        use_hawkears=use_hawkears,
        hawkears_args=extra_args,
    )
    console.print(f"Processed {len(jobs)} jobs; outputs stored in {output_dir}")


def _run_scheduler(
    jobs: Sequence[InferenceJob],
    worker_pool: list[GPUWorker | None],
    output_dir: Path,
    runner_cmd: str | None,
    max_retries: int,
    use_hawkears: bool,
    hawkears_args: Sequence[str],
) -> None:
    if not worker_pool:
        worker_pool = [None]
    job_queue: queue.Queue = queue.Queue()
    sentinel = object()
    for job in jobs:
        job_queue.put(job)
    for _ in worker_pool:
        job_queue.put(sentinel)

    stop_event = threading.Event()
    errors: list[Exception] = []
    runner_args = list(hawkears_args)

    def worker_loop(worker: GPUWorker | None) -> None:
        while True:
            job = job_queue.get()
            try:
                if job is sentinel:
                    return
                if stop_event.is_set():
                    continue
                run_job(
                    job=job,
                    worker=worker,  # type: ignore[arg-type]
                    output_dir=output_dir,
                    runner_cmd=runner_cmd,
                    max_retries=max_retries,
                    use_hawkears=use_hawkears,
                    hawkears_args=runner_args,
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
) -> None:
    """Aggregate detection JSON files into a summary CSV."""

    from badc.aggregate import load_detections, write_summary_csv

    records = load_detections(detections_dir)
    if not records:
        console.print("No detections found.", style="yellow")
        return
    summary_path = write_summary_csv(records, output)
    console.print(f"Wrote detection summary to {summary_path}")


def main() -> None:
    """Entrypoint used by the console script."""

    app()


@app.command("telemetry")
def telemetry_monitor(
    log_path: Annotated[
        Path,
        typer.Option("--log", help="Telemetry log path."),
    ] = Path("data/telemetry/infer/log.jsonl"),
) -> None:
    """Display recent telemetry entries."""

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
