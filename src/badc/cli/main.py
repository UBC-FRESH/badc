"""Primary Typer CLI for the Bird Acoustic Data Cruncher project."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from badc import __version__, chunking

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
    name: Annotated[
        str,
        typer.Argument(help="Logical dataset name (e.g., 'bogus', 'production')."),
    ],
    path: Annotated[
        Path | None,
        typer.Option("--path", help="Local path where the dataset should be cloned or registered."),
    ] = None,
) -> None:
    """Stub for future DataLad dataset attach workflow."""

    target_path = path or (Path.cwd() / DEFAULT_DATALAD_PATH)
    console.print(
        "[yellow]TODO:[/] implement DataLad clone/register logic.",
        style="bold",
    )
    console.print(f"Requested dataset: [cyan]{name}[/] @ {target_path}")


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


@infer_app.command("run")
def infer_run(
    chunk_ids: Annotated[
        list[str],
        typer.Argument(
            help="Chunk identifiers to process (placeholder; eventually derived from chunk outputs)."
        ),
    ],
) -> None:
    """Placeholder inference command."""

    detections = chunking.run_inference_on_chunks(chunk_ids)
    console.print("Inference placeholder complete:")
    for det in detections:
        console.print(f" - {det}")


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
