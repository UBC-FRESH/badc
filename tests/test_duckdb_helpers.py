from __future__ import annotations

from pathlib import Path

import pytest

from badc import duckdb_helpers

duckdb = pytest.importorskip("duckdb")
pd = pytest.importorskip("pandas")


def _build_bundle(db_path: Path) -> None:
    con = duckdb.connect(str(db_path))
    con.execute(
        """
        CREATE TABLE detections (
            recording_id TEXT,
            chunk_id TEXT,
            chunk_start_ms BIGINT,
            label TEXT,
            label_name TEXT,
            confidence DOUBLE
        )
        """
    )
    rows = [
        ("recA", "chunk_a", 0, "WTSP", "White-throated Sparrow", 0.9),
        ("recA", "chunk_b", 60000, "WTSP", "White-throated Sparrow", 0.85),
        ("recB", "chunk_c", 0, "NOCA", "Northern Cardinal", 0.7),
    ]
    con.executemany("INSERT INTO detections VALUES (?, ?, ?, ?, ?, ?)", rows)
    bucket_ms = 30 * 60 * 1000
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
    con.close()


def test_verify_bundle_schema_passes(tmp_path: Path) -> None:
    db_path = tmp_path / "bundle.duckdb"
    _build_bundle(db_path)
    duckdb_helpers.verify_bundle_schema(db_path)


def test_verify_bundle_schema_missing_view(tmp_path: Path) -> None:
    db_path = tmp_path / "bundle.duckdb"
    con = duckdb.connect(str(db_path))
    con.execute("CREATE TABLE detections(recording_id TEXT)")
    con.close()
    with pytest.raises(RuntimeError):
        duckdb_helpers.verify_bundle_schema(db_path)


def test_load_duckdb_views_returns_dataframes(tmp_path: Path) -> None:
    db_path = tmp_path / "bundle.duckdb"
    _build_bundle(db_path)
    views = duckdb_helpers.load_duckdb_views(db_path, limit_labels=1, limit_recordings=1)
    assert isinstance(views.label_summary, pd.DataFrame)
    assert isinstance(views.recording_summary, pd.DataFrame)
    assert isinstance(views.timeline_summary, pd.DataFrame)
    assert views.label_summary.iloc[0]["label"] == "WTSP"
    assert views.recording_summary.iloc[0]["recording_id"] == "recA"
    assert set(views.timeline_summary.columns) == {
        "bucket_index",
        "bucket_start_ms",
        "detections",
        "avg_confidence",
    }
