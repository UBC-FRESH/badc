"""Primary Typer CLI for the Bird Acoustic Data Cruncher project."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from badc import __version__, chunking
from badc.audio import get_wav_duration
from badc.chunk_writer import ChunkMetadata, iter_chunk_metadata
from badc.gpu import detect_gpus
from badc.infer_scheduler import GPUWorker, load_jobs, plan_workers

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
) -> None:
    """Stub for future DataLad dataset attach workflow."""

    target_path = path / name
    console.print("[yellow]TODO:[/] implement DataLad clone/register logic.", style="bold")
    console.print(f"Dataset: [cyan]{name}[/] -> {target_path}")


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
) -> None:
    """Stub for future DataLad dataset detach workflow."""

    status = "drop content" if drop_content else "keep content"
    console.print(
        "[yellow]TODO:[/] implement DataLad drop/unregister logic.",
        style="bold",
    )
    console.print(f"Requested dataset: [cyan]{name}[/] ({status}).")


@data_app.command("status")
def data_status() -> None:
    """Placeholder for reporting attached DataLad datasets."""

    console.print("[yellow]TODO:[/] list connected datasets and their availability.")


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
) -> None:
    """Placeholder inference command using manifest."""

    jobs = load_jobs(manifest)
    workers = plan_workers(max_gpus=max_gpus)
    from badc.hawkears_runner import run_job

    if not jobs:
        console.print("No jobs found in manifest.", style="yellow")
        return
    worker_pool: list[GPUWorker | None]
    if not workers:
        console.print("No GPUs detected; running without GPU affinity.", style="yellow")
        worker_pool = [None]
    else:
        worker_pool = workers

    processed = 0
    for idx, job in enumerate(jobs):
        worker = worker_pool[idx % len(worker_pool)]
        run_job(
            job=job,
            worker=worker,  # type: ignore[arg-type]
            output_dir=output_dir,
            runner_cmd=runner_cmd,
            max_retries=max_retries,
        )
        processed += 1
    console.print(f"Processed {processed} jobs; outputs stored in {output_dir}")


@infer_app.command("aggregate")
def infer_aggregate(
    detection_ids: Annotated[
        list[str],
        typer.Argument(help="Detection IDs to aggregate (placeholder)."),
    ],
) -> None:
    """Placeholder aggregation command."""

    summary = chunking.aggregate_detections(detection_ids)
    console.print("Aggregation placeholder summary:")
    for chunk_name, count in summary.items():
        console.print(f" - {chunk_name}: {count} detections")


def main() -> None:
    """Entrypoint used by the console script."""

    app()
