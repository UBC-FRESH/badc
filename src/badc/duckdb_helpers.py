"""Helpers for loading DuckDB bundle outputs produced by ``badc report bundle``.

The aggregation/report stage (see ``notes/pipeline-plan.md``) leaves behind a
per-recording DuckDB database containing the canonical detections table plus
three convenience views:

* ``label_summary`` (counts + average confidence per label)
* ``recording_summary`` (counts per recording)
* ``timeline_summary`` (bucketed detections, e.g., 30-minute windows)

This module provides a small Python API that notebooks/tests can reuse to read
those views without duplicating SQL. DuckDB and pandas remain optional runtime
dependencies; callers should install them via ``pip install duckdb pandas`` when
using these helpers.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

try:  # pragma: no cover - dependency probe
    import duckdb  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - dependency probe
    duckdb = None

try:  # pragma: no cover - dependency probe
    import pandas as pd  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - dependency probe
    pd = None


@dataclass(slots=True)
class DuckDBViews:
    """Container for the canonical DuckDB summary views.

    Attributes
    ----------
    label_summary
        pandas DataFrame mirroring the ``label_summary`` view. Columns:
        ``label``, ``label_name``, ``detections``, ``avg_confidence``.
    recording_summary
        pandas DataFrame mirroring the ``recording_summary`` view. Columns:
        ``recording_id``, ``detections``, ``avg_confidence``.
    timeline_summary
        pandas DataFrame mirroring the ``timeline_summary`` view. Columns:
        ``bucket_index``, ``bucket_start_ms``, ``detections``, ``avg_confidence``.
    """

    label_summary: "pd.DataFrame"
    recording_summary: "pd.DataFrame"
    timeline_summary: "pd.DataFrame"


def _require_dependencies() -> None:
    missing: list[str] = []
    if duckdb is None:
        missing.append("duckdb")
    if pd is None:
        missing.append("pandas")
    if missing:
        raise RuntimeError(
            f"{', '.join(missing)} required for DuckDB helpers. Install with `pip install {' '.join(missing)}`."
        )


def _connect(database: Path | str):
    _require_dependencies()
    db_path = Path(database).expanduser()
    if not db_path.exists():
        raise FileNotFoundError(db_path)
    return duckdb.connect(str(db_path))


def verify_bundle_schema(database: Path | str) -> None:
    """Validate that the bundle database includes the expected table + views.

    Parameters
    ----------
    database
        Path to the DuckDB file produced by ``badc report bundle`` or
        ``badc report duckdb``.

    Raises
    ------
    FileNotFoundError
        If the database path does not exist.
    RuntimeError
        When required objects (``detections`` table or summary views) are missing.
    """

    con = _connect(database)
    try:
        table_names = {
            row[0]
            for row in con.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'"
            ).fetchall()
        }
        view_names = {
            row[0]
            for row in con.execute(
                "SELECT table_name FROM information_schema.views WHERE table_schema = 'main'"
            ).fetchall()
        }
    finally:
        con.close()

    missing_tables = {"detections"} - table_names
    missing_views = {"label_summary", "recording_summary", "timeline_summary"} - view_names
    if missing_tables or missing_views:
        problems = []
        if missing_tables:
            problems.append(f"tables: {sorted(missing_tables)}")
        if missing_views:
            problems.append(f"views: {sorted(missing_views)}")
        raise RuntimeError(
            "DuckDB bundle schema incomplete; missing " + ", ".join(problems) + ". "
            "Re-run `badc report bundle` to regenerate the database."
        )


def load_duckdb_views(
    database: Path | str,
    *,
    limit_labels: Optional[int] = None,
    limit_recordings: Optional[int] = None,
) -> DuckDBViews:
    """Load the canonical DuckDB summary views into pandas DataFrames.

    Parameters
    ----------
    database
        Path to the DuckDB file produced by ``badc report bundle``.
    limit_labels : int, optional
        Optional cap for the number of label rows returned.
    limit_recordings : int, optional
        Optional cap for the number of recording rows returned.

    Returns
    -------
    DuckDBViews
        Dataclass containing the three summary DataFrames.
    """

    verify_bundle_schema(database)
    con = _connect(database)
    try:
        label_query = "SELECT * FROM label_summary ORDER BY detections DESC"
        if limit_labels:
            label_query += f" LIMIT {max(1, limit_labels)}"
        label_df = con.execute(label_query).df()

        recording_query = "SELECT * FROM recording_summary ORDER BY detections DESC"
        if limit_recordings:
            recording_query += f" LIMIT {max(1, limit_recordings)}"
        recording_df = con.execute(recording_query).df()

        timeline_df = con.execute(
            "SELECT * FROM timeline_summary ORDER BY bucket_start_ms, bucket_index"
        ).df()
    finally:
        con.close()

    return DuckDBViews(
        label_summary=label_df,
        recording_summary=recording_df,
        timeline_summary=timeline_df,
    )
