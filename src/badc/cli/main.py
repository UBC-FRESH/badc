"""Primary Typer CLI for the Bird Acoustic Data Cruncher project."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from badc import __version__

console = Console()
app = typer.Typer(help="Utilities for chunking and processing large bird audio corpora.")
DEFAULT_DATALAD_PATH = Path("data") / "datalad"

data_app = typer.Typer(help="Manage DataLad-backed audio repositories (stub commands).")
app.add_typer(data_app, name="data")


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


def main() -> None:
    """Entrypoint used by the console script."""

    app()
