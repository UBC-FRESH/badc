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
    chunk_start_ms: int | None
    chunk_end_ms: int | None
    timestamp_ms: int | None
    absolute_time_ms: int | None
    label: str
    confidence: float | None
    status: str
    runner: str | None
    chunk_sha256: str | None
    source_path: Path
    dataset_root: Path | None


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
    if isinstance(detections, list) and detections:
        for det in detections:
            rel_ts = _to_int(det.get("timestamp_ms"))
            abs_ts = None
            if chunk_start is not None and rel_ts is not None:
                abs_ts = chunk_start + rel_ts
            records.append(
                DetectionRecord(
                    recording_id=recording_id,
                    chunk_id=chunk_id,
                    chunk_start_ms=chunk_start,
                    chunk_end_ms=chunk_end,
                    timestamp_ms=rel_ts,
                    absolute_time_ms=abs_ts,
                    label=str(det.get("label", "unknown")),
                    confidence=float(det.get("confidence", 0.0))
                    if det.get("confidence") is not None
                    else None,
                    status="ok",
                    runner=runner,
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
                label="none",
                confidence=None,
                status=data.get("status", "unknown"),
                runner=runner,
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
        "timestamp_ms,absolute_time_ms,label,confidence,status,runner,source_path"
    ]
    for rec in records:
        ts = "" if rec.timestamp_ms is None else rec.timestamp_ms
        abs_ts = "" if rec.absolute_time_ms is None else rec.absolute_time_ms
        conf = "" if rec.confidence is None else rec.confidence
        chunk_start = "" if rec.chunk_start_ms is None else rec.chunk_start_ms
        chunk_end = "" if rec.chunk_end_ms is None else rec.chunk_end_ms
        runner = rec.runner or ""
        lines.append(
            f"{rec.recording_id},{rec.chunk_id},{chunk_start},{chunk_end},"
            f"{ts},{abs_ts},{rec.label},{conf},{rec.status},{runner},{rec.source_path}"
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
            label TEXT,
            confidence DOUBLE,
            status TEXT,
            runner TEXT,
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
            rec.label,
            rec.confidence,
            rec.status,
            rec.runner,
            rec.chunk_sha256,
            str(rec.source_path),
            str(rec.dataset_root) if rec.dataset_root else None,
        )
        for rec in records
    ]
    if rows:
        con.executemany(
            """
            INSERT INTO detections VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
