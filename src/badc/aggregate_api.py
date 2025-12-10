"""High-level helpers for working with canonical detection artifacts in Python.

The Typer CLI exposes aggregation/report commands, but notebooks/tests often
need a lightweight API that returns ``DetectionRecord`` objects or pandas
DataFrames without shelling out to the CLI.  This module wraps the underlying
:mod:`badc.aggregate` functions plus :mod:`badc.duckdb_helpers` so downstream
code can load detections, write CSV/Parquet artifacts, and open DuckDB bundles
directly.
"""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Sequence

from badc import aggregate
from badc.duckdb_helpers import DuckDBViews, load_duckdb_views

try:  # pragma: no cover - optional dependency
    import pandas as pd  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    pd = None  # type: ignore[assignment]

DetectionRecords = list[aggregate.DetectionRecord]


def _ensure_pandas() -> None:
    if pd is None:
        raise RuntimeError(
            "pandas is required for DataFrame helpers. Install with `pip install pandas`."
        )


def load_detection_records(
    detections_dir: Path | str,
    manifest: Path | str | None = None,
) -> DetectionRecords:
    """Return canonical detection records for ``detections_dir``.

    Parameters
    ----------
    detections_dir
        Directory containing per-chunk JSON files (typically
        ``<dataset>/artifacts/infer``).
    manifest
        Optional manifest CSV used to fill in chunk metadata. When omitted, only
        JSON-provided metadata is used.
    """

    detections_path = Path(detections_dir).expanduser()
    manifest_path = Path(manifest).expanduser() if manifest else None
    return aggregate.load_detections(detections_path, manifest=manifest_path)


def detections_to_dataframe(records: Sequence[aggregate.DetectionRecord]):
    """Convert ``DetectionRecord`` objects into a pandas DataFrame."""

    _ensure_pandas()
    rows = []
    for record in records:
        row = asdict(record)
        source_path = row["source_path"]
        row["source_path"] = str(source_path) if source_path else None
        dataset_root = row["dataset_root"]
        row["dataset_root"] = str(dataset_root) if dataset_root else None
        rows.append(row)
    return pd.DataFrame(rows)


def load_detection_dataframe(
    detections_dir: Path | str,
    manifest: Path | str | None = None,
):
    """Load detection records directly into a pandas DataFrame."""

    records = load_detection_records(detections_dir, manifest=manifest)
    return detections_to_dataframe(records)


def aggregate_inference_outputs(
    detections_dir: Path | str,
    *,
    manifest: Path | str | None = None,
    summary_csv: Path | str | None = None,
    parquet: Path | str | None = None,
) -> DetectionRecords:
    """Load detections and optionally write CSV/Parquet artifacts.

    Parameters
    ----------
    detections_dir
        Directory containing the JSON outputs produced by ``badc infer run``.
    manifest
        Optional manifest CSV used to fill in missing metadata.
    summary_csv
        When provided, writes ``DetectionRecord`` entries to a CSV file matching
        the CLI output of ``badc infer aggregate``.
    parquet
        Optional Parquet destination (uses DuckDB) mirroring the CLI behavior.

    Returns
    -------
    list of DetectionRecord
        The canonical detection entries, suitable for further in-memory analysis.
    """

    records = load_detection_records(detections_dir, manifest=manifest)
    if summary_csv:
        aggregate.write_summary_csv(records, Path(summary_csv).expanduser())
    if parquet:
        aggregate.write_parquet(records, Path(parquet).expanduser())
    return records


def load_bundle_views(
    database: Path | str,
    *,
    limit_labels: int | None = None,
    limit_recordings: int | None = None,
) -> DuckDBViews:
    """Return pandas DataFrames for a DuckDB bundle produced by ``badc report bundle``."""

    return load_duckdb_views(
        database,
        limit_labels=limit_labels,
        limit_recordings=limit_recordings,
    )


__all__ = [
    "DetectionRecords",
    "aggregate_inference_outputs",
    "detections_to_dataframe",
    "load_bundle_views",
    "load_detection_dataframe",
    "load_detection_records",
    "DuckDBViews",
]
