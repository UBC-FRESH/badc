"""Detection aggregation utilities."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Sequence

from badc.data import find_dataset_root


@dataclass
class DetectionRecord:
    """Normalized detection entry used for CSV summaries."""

    recording_id: str
    chunk_id: str
    label: str
    status: str
    source_path: Path
    chunk_start_ms: int | None = None
    chunk_end_ms: int | None = None
    timestamp_ms: int | None = None
    absolute_time_ms: int | None = None
    detection_end_ms: int | None = None
    absolute_end_ms: int | None = None
    label_code: str | None = None
    label_name: str | None = None
    confidence: float | None = None
    runner: str | None = None
    model_version: str | None = None
    chunk_sha256: str | None = None
    dataset_root: Path | None = None


@dataclass
class QuicklookReport:
    """Convenience container for DuckDB quicklook metrics."""

    top_labels: list[tuple[str, str | None, int, float | None]]
    top_recordings: list[tuple[str, int, float | None]]
    chunk_timeline: list[tuple[str, int | None, int, float | None]]


@dataclass
class ParquetReport:
    """Structured summary produced by :func:`parquet_report`."""

    labels: list[tuple[str, str | None, int, float | None]]
    recordings: list[tuple[str, int, float | None]]
    timeline: list[tuple[str, int | None, int, float | None]]
    summary: dict[str, int | float | None]


@dataclass
class _ManifestRecord:
    """Subset of manifest metadata used to enrich detections."""

    chunk_id: str
    recording_id: str | None
    source_path: Path | None
    start_ms: int | None
    end_ms: int | None
    overlap_ms: int | None
    sha256: str | None


def _parse_detection_entries(
    data: dict,
    recording_id: str,
    chunk_id: str,
    json_path: Path,
    manifest_row: _ManifestRecord | None = None,
) -> list[DetectionRecord]:
    records: list[DetectionRecord] = []
    chunk_info = data.get("chunk") or {}
    chunk_start = _coalesce(
        _to_int(chunk_info.get("start_ms")), manifest_row.start_ms if manifest_row else None
    )
    chunk_end = _coalesce(
        _to_int(chunk_info.get("end_ms")), manifest_row.end_ms if manifest_row else None
    )
    sha256 = chunk_info.get("sha256") or (manifest_row.sha256 if manifest_row else None)
    runner = data.get("runner")
    dataset_root = Path(data["dataset_root"]) if data.get("dataset_root") else None
    chunk_source = data.get("source_path")
    if not chunk_source and manifest_row and manifest_row.source_path:
        chunk_source = manifest_row.source_path
    source_path = Path(chunk_source) if chunk_source else json_path
    if dataset_root is None and chunk_source:
        dataset_root = find_dataset_root(Path(chunk_source))
    detections = data.get("detections")
    model_version = data.get("model_version")
    if isinstance(detections, list) and detections:
        for det in detections:
            rel_ts = _to_int(det.get("timestamp_ms"))
            rel_end = _to_int(det.get("end_ms"))
            abs_ts = None
            if chunk_start is not None and rel_ts is not None:
                abs_ts = chunk_start + rel_ts
            abs_end = None
            if chunk_start is not None and rel_end is not None:
                abs_end = chunk_start + rel_end
            records.append(
                DetectionRecord(
                    recording_id=recording_id,
                    chunk_id=chunk_id,
                    chunk_start_ms=chunk_start,
                    chunk_end_ms=chunk_end,
                    timestamp_ms=rel_ts,
                    absolute_time_ms=abs_ts,
                    detection_end_ms=rel_end,
                    absolute_end_ms=abs_end,
                    label=str(det.get("label", "unknown")),
                    label_code=det.get("label_code"),
                    label_name=det.get("label_name"),
                    confidence=float(det.get("confidence", 0.0))
                    if det.get("confidence") is not None
                    else None,
                    status="ok",
                    runner=runner,
                    model_version=model_version,
                    chunk_sha256=sha256,
                    source_path=source_path,
                    dataset_root=dataset_root,
                )
            )
    else:
        records.append(
            DetectionRecord(
                recording_id=recording_id,
                chunk_id=chunk_id,
                chunk_start_ms=chunk_start,
                chunk_end_ms=chunk_end,
                timestamp_ms=None,
                absolute_time_ms=None,
                detection_end_ms=None,
                absolute_end_ms=None,
                label="none",
                label_code=None,
                label_name=None,
                confidence=None,
                status=data.get("status", "unknown"),
                runner=runner,
                model_version=model_version,
                chunk_sha256=sha256,
                source_path=source_path,
                dataset_root=dataset_root,
            )
        )
    return records


def load_detections(root: Path, manifest: Path | None = None) -> List[DetectionRecord]:
    """Load detection JSON payloads under ``root``.

    Parameters
    ----------
    root
        Directory containing per-chunk JSON files (one per inference run).
    manifest
        Optional chunk manifest used to fill in missing chunk metadata.

    Returns
    -------
    list of DetectionRecord
        Parsed detections, one record per event or status placeholder.
    """

    manifest_map: Dict[str, _ManifestRecord] = _load_manifest_index(manifest) if manifest else {}
    records: List[DetectionRecord] = []
    for path in root.rglob("*.json"):
        try:
            data = json.loads(path.read_text())
        except json.JSONDecodeError:
            continue
        chunk_id = data.get("chunk_id", path.stem)
        manifest_row = manifest_map.get(chunk_id)
        recording_id = data.get("recording_id") or (
            manifest_row.recording_id
            if manifest_row and manifest_row.recording_id
            else path.parent.name
        )
        records.extend(_parse_detection_entries(data, recording_id, chunk_id, path, manifest_row))
    return records


def write_summary_csv(records: Iterable[DetectionRecord], out_path: Path) -> Path:
    """Write detection records to ``out_path`` in CSV form.

    Parameters
    ----------
    records
        Iterable of :class:`DetectionRecord` objects.
    out_path
        Destination CSV path. Parent directories are created automatically.

    Returns
    -------
    Path
        The ``out_path`` provided (for chaining).
    """

    lines = [
        "recording_id,chunk_id,chunk_start_ms,chunk_end_ms,"
        "timestamp_ms,absolute_time_ms,end_ms,absolute_end_ms,"
        "label,label_code,label_name,confidence,status,runner,model_version,"
        "chunk_sha256,source_path,dataset_root"
    ]
    for rec in records:
        ts = "" if rec.timestamp_ms is None else rec.timestamp_ms
        abs_ts = "" if rec.absolute_time_ms is None else rec.absolute_time_ms
        end_ts = "" if rec.detection_end_ms is None else rec.detection_end_ms
        abs_end = "" if rec.absolute_end_ms is None else rec.absolute_end_ms
        conf = "" if rec.confidence is None else rec.confidence
        chunk_start = "" if rec.chunk_start_ms is None else rec.chunk_start_ms
        chunk_end = "" if rec.chunk_end_ms is None else rec.chunk_end_ms
        runner = rec.runner or ""
        label_code = rec.label_code or ""
        label_name = rec.label_name or ""
        model_version = rec.model_version or ""
        chunk_sha = rec.chunk_sha256 or ""
        dataset_root = "" if rec.dataset_root is None else str(rec.dataset_root)
        lines.append(
            f"{rec.recording_id},{rec.chunk_id},{chunk_start},{chunk_end},"
            f"{ts},{abs_ts},{end_ts},{abs_end},{rec.label},{label_code},{label_name},"
            f"{conf},{rec.status},{runner},{model_version},{chunk_sha},{rec.source_path},{dataset_root}"
        )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n")
    return out_path


def write_parquet(records: Sequence[DetectionRecord], out_path: Path) -> Path:
    """Persist detection records to Parquet via DuckDB."""

    try:
        import duckdb  # type: ignore
    except ModuleNotFoundError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError(
            "duckdb is required for Parquet export. Install with `pip install duckdb`."
        ) from exc

    out_path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute(
        """
        CREATE TABLE detections (
            recording_id TEXT,
            chunk_id TEXT,
            chunk_start_ms BIGINT,
            chunk_end_ms BIGINT,
            timestamp_ms BIGINT,
            absolute_time_ms BIGINT,
            end_ms BIGINT,
            absolute_end_ms BIGINT,
            label TEXT,
            label_code TEXT,
            label_name TEXT,
            confidence DOUBLE,
            status TEXT,
            runner TEXT,
            model_version TEXT,
            chunk_sha256 TEXT,
            source_path TEXT,
            dataset_root TEXT
        )
        """
    )
    rows = [
        (
            rec.recording_id,
            rec.chunk_id,
            rec.chunk_start_ms,
            rec.chunk_end_ms,
            rec.timestamp_ms,
            rec.absolute_time_ms,
            rec.detection_end_ms,
            rec.absolute_end_ms,
            rec.label,
            rec.label_code,
            rec.label_name,
            rec.confidence,
            rec.status,
            rec.runner,
            rec.model_version,
            rec.chunk_sha256,
            str(rec.source_path),
            str(rec.dataset_root) if rec.dataset_root else None,
        )
        for rec in records
    ]
    if rows:
        con.executemany(
            """
            INSERT INTO detections VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            rows,
        )
    con.execute(f"COPY detections TO '{out_path}' (FORMAT PARQUET)")
    con.close()
    return out_path


def summarize_parquet(
    parquet_path: Path,
    *,
    group_by: Sequence[str] | None = None,
) -> List[tuple]:
    """Return aggregated metrics from the Parquet detections file.

    Parameters
    ----------
    parquet_path
        Path to the Parquet file containing canonical detections as produced by
        :func:`write_parquet`.
    group_by
        Columns to aggregate by. Supported values are ``"label"`` and
        ``"recording_id"``. When ``None`` or empty the function defaults to
        grouping by label.

    Returns
    -------
    list of tuple
        Rows containing the requested grouping columns plus ``detections`` and
        ``avg_confidence``.
    """

    try:
        import duckdb  # type: ignore
    except ModuleNotFoundError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError(
            "duckdb is required to summarize detections. Install with `pip install duckdb`."
        ) from exc

    valid_columns = {"recording_id", "label"}
    selected = list(group_by) if group_by else ["label"]
    invalid = [col for col in selected if col not in valid_columns]
    if invalid:
        raise ValueError(f"Unsupported group-by columns: {', '.join(invalid)}")

    select_cols = ", ".join(selected)
    group_cols = ", ".join(selected)
    query = f"""
        SELECT {select_cols},
               COUNT(*) AS detections,
               AVG(confidence) AS avg_confidence
        FROM read_parquet(?)
        GROUP BY {group_cols}
        ORDER BY detections DESC
    """
    con = duckdb.connect()
    rows = con.execute(query, [str(parquet_path)]).fetchall()
    con.close()
    return rows


def quicklook_metrics(
    parquet_path: Path,
    *,
    top_labels: int = 10,
    top_recordings: int | None = None,
) -> QuicklookReport:
    """Return multi-table summary metrics from the canonical Parquet export.

    Parameters
    ----------
    parquet_path
        Path to the canonical detections Parquet file.
    top_labels
        Number of label rows to include in the quicklook summary (default 10).
    top_recordings
        Number of recording rows to include. When ``None`` this mirrors ``top_labels``.

    Returns
    -------
    QuicklookReport
        Container with top labels, top recordings, and a per-chunk timeline suitable for
        ASCII or graphical plots.
    """

    try:
        import duckdb  # type: ignore
    except ModuleNotFoundError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError(
            "duckdb is required for quicklook summaries. Install with `pip install duckdb`."
        ) from exc

    limit_labels = max(1, top_labels)
    limit_recordings = max(1, top_recordings or top_labels)
    con = duckdb.connect()
    label_rows = con.execute(
        """
        SELECT label,
               COALESCE(label_name, '') AS label_name,
               COUNT(*) AS detections,
               AVG(confidence) AS avg_confidence
        FROM read_parquet(?)
        GROUP BY label, label_name
        ORDER BY detections DESC
        LIMIT ?
        """,
        [str(parquet_path), limit_labels],
    ).fetchall()
    recording_rows = con.execute(
        """
        SELECT recording_id,
               COUNT(*) AS detections,
               AVG(confidence) AS avg_confidence
        FROM read_parquet(?)
        GROUP BY recording_id
        ORDER BY detections DESC
        LIMIT ?
        """,
        [str(parquet_path), limit_recordings],
    ).fetchall()
    chunk_rows = con.execute(
        """
        SELECT chunk_id,
               MIN(chunk_start_ms) AS chunk_start_ms,
               COUNT(*) AS detections,
               AVG(confidence) AS avg_confidence
        FROM read_parquet(?)
        GROUP BY chunk_id
        ORDER BY chunk_start_ms NULLS FIRST, chunk_id
        """,
        [str(parquet_path)],
    ).fetchall()
    con.close()
    label_cast = [
        (row[0], row[1] or None, int(row[2]), float(row[3]) if row[3] is not None else None)
        for row in label_rows
    ]
    recording_cast = [
        (row[0] or "unknown", int(row[1]), float(row[2]) if row[2] is not None else None)
        for row in recording_rows
    ]
    chunk_cast = [
        (
            row[0],
            int(row[1]) if row[1] is not None else None,
            int(row[2]),
            float(row[3]) if row[3] is not None else None,
        )
        for row in chunk_rows
    ]
    return QuicklookReport(
        top_labels=label_cast,
        top_recordings=recording_cast,
        chunk_timeline=chunk_cast,
    )


def parquet_report(
    parquet_path: Path,
    *,
    top_labels: int = 20,
    top_recordings: int = 10,
    bucket_minutes: int = 60,
) -> ParquetReport:
    """Summarize canonical detections using DuckDB."""

    try:
        import duckdb  # type: ignore
    except ModuleNotFoundError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError(
            "duckdb is required for parquet reports. Install with `pip install duckdb`."
        ) from exc

    bucket_minutes = max(1, bucket_minutes)
    bucket_ms = bucket_minutes * 60 * 1000
    con = duckdb.connect()
    label_rows = con.execute(
        """
        SELECT label,
               COALESCE(label_name, '') AS label_name,
               COUNT(*) AS detections,
               AVG(confidence) AS avg_confidence
        FROM read_parquet(?)
        GROUP BY label, label_name
        ORDER BY detections DESC
        LIMIT ?
        """,
        [str(parquet_path), max(1, top_labels)],
    ).fetchall()
    recording_rows = con.execute(
        """
        SELECT recording_id,
               COUNT(*) AS detections,
               AVG(confidence) AS avg_confidence
        FROM read_parquet(?)
        GROUP BY recording_id
        ORDER BY detections DESC
        LIMIT ?
        """,
        [str(parquet_path), max(1, top_recordings)],
    ).fetchall()
    timeline_rows = con.execute(
        """
        WITH chunk_data AS (
            SELECT chunk_id,
                   COALESCE(chunk_start_ms, 0) AS chunk_start_ms,
                   CAST(FLOOR(COALESCE(chunk_start_ms, 0) / ?) AS BIGINT) AS bucket_index,
                   COUNT(*) AS detections,
                   AVG(confidence) AS avg_confidence
            FROM read_parquet(?)
            GROUP BY chunk_id, chunk_start_ms, bucket_index
        )
        SELECT bucket_index,
               MIN(chunk_start_ms) AS bucket_start_ms,
               SUM(detections) AS detections,
               AVG(avg_confidence) AS avg_confidence
        FROM chunk_data
        GROUP BY bucket_index
        ORDER BY bucket_start_ms, bucket_index
        """,
        [bucket_ms, str(parquet_path)],
    ).fetchall()
    summary_row = con.execute(
        """
        SELECT COUNT(*) AS detections,
               COUNT(DISTINCT label) AS label_count,
               COUNT(DISTINCT recording_id) AS recording_count,
               MIN(chunk_start_ms) AS first_chunk_ms,
               MAX(chunk_start_ms) AS last_chunk_ms
        FROM read_parquet(?)
        """,
        [str(parquet_path)],
    ).fetchone()
    con.close()

    label_cast = [
        (row[0], row[1] or None, int(row[2]), float(row[3]) if row[3] is not None else None)
        for row in label_rows
    ]
    recording_cast = [
        (row[0] or "unknown", int(row[1]), float(row[2]) if row[2] is not None else None)
        for row in recording_rows
    ]
    timeline_cast = [
        (
            f"bucket_{row[0]}",
            int(row[1]) if row[1] is not None else None,
            int(row[2]),
            float(row[3]) if row[3] is not None else None,
        )
        for row in timeline_rows
    ]
    summary = {
        "detections": int(summary_row[0]) if summary_row and summary_row[0] is not None else 0,
        "label_count": int(summary_row[1]) if summary_row and summary_row[1] is not None else 0,
        "recording_count": int(summary_row[2]) if summary_row and summary_row[2] is not None else 0,
        "first_chunk_ms": (
            int(summary_row[3]) if summary_row and summary_row[3] is not None else None
        ),
        "last_chunk_ms": (
            int(summary_row[4]) if summary_row and summary_row[4] is not None else None
        ),
        "bucket_minutes": bucket_minutes,
    }
    return ParquetReport(
        labels=label_cast,
        recordings=recording_cast,
        timeline=timeline_cast,
        summary=summary,
    )


def _load_manifest_index(manifest: Path | None) -> Dict[str, _ManifestRecord]:
    if manifest is None:
        return {}
    index: Dict[str, _ManifestRecord] = {}
    with manifest.open() as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            chunk_id = row.get("chunk_id")
            if not chunk_id:
                continue
            source_path = Path(row["source_path"]).expanduser() if row.get("source_path") else None
            index[chunk_id] = _ManifestRecord(
                chunk_id=chunk_id,
                recording_id=row.get("recording_id") or None,
                source_path=source_path,
                start_ms=_to_int(row.get("start_ms")),
                end_ms=_to_int(row.get("end_ms")),
                overlap_ms=_to_int(row.get("overlap_ms")),
                sha256=row.get("sha256") or None,
            )
    return index


def _coalesce(*values: int | None) -> int | None:
    for value in values:
        if value is not None:
            return value
    return None


def _to_int(value: object) -> int | None:
    if value in (None, "", "NA"):
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None
