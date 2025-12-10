from __future__ import annotations

import json
from pathlib import Path

import pytest

from badc import aggregate_api


def _write_inference_payload(root: Path) -> Path:
    infer_dir = root / "artifacts" / "infer" / "rec1"
    infer_dir.mkdir(parents=True)
    payload = {
        "chunk_id": "rec1_chunk_0_500",
        "recording_id": "rec1",
        "source_path": str(infer_dir / "rec1_chunk_0_500.wav"),
        "status": "ok",
        "runner": "hawkears",
        "chunk": {"start_ms": 0, "end_ms": 500, "sha256": "abc123"},
        "detections": [
            {
                "timestamp_ms": 50,
                "end_ms": 100,
                "label": "WTSP",
                "label_code": "WTSP",
                "label_name": "White-throated Sparrow",
                "confidence": 0.9,
            }
        ],
    }
    (infer_dir / "rec1_chunk.json").write_text(json.dumps(payload), encoding="utf-8")
    return infer_dir.parent


def test_load_detection_records(tmp_path: Path) -> None:
    infer_root = _write_inference_payload(tmp_path)
    records = aggregate_api.load_detection_records(infer_root)
    assert len(records) == 1
    assert records[0].label_code == "WTSP"


def test_load_detection_dataframe(tmp_path: Path) -> None:
    pytest.importorskip("pandas")
    infer_root = _write_inference_payload(tmp_path)
    df = aggregate_api.load_detection_dataframe(infer_root)
    assert df.shape[0] == 1
    assert df["label_code"].iloc[0] == "WTSP"


def test_aggregate_inference_outputs_writes_artifacts(tmp_path: Path) -> None:
    infer_root = _write_inference_payload(tmp_path)
    summary_csv = tmp_path / "summary.csv"
    parquet_path = tmp_path / "detections.parquet"
    records = aggregate_api.aggregate_inference_outputs(
        infer_root, summary_csv=summary_csv, parquet=parquet_path
    )
    assert len(records) == 1
    assert summary_csv.exists()
    pytest.importorskip("duckdb")
    assert parquet_path.exists()


def test_load_bundle_views(tmp_path: Path) -> None:
    duckdb = pytest.importorskip("duckdb")
    db_path = tmp_path / "bundle.duckdb"
    con = duckdb.connect(str(db_path))
    try:
        con.execute(
            """
            CREATE TABLE detections (
                recording_id TEXT,
                label TEXT,
                label_name TEXT,
                confidence DOUBLE
            )
            """
        )
        con.execute(
            """
            INSERT INTO detections VALUES
                ('rec1', 'WTSP', 'White-throated Sparrow', 0.9),
                ('rec1', 'WTSP', 'White-throated Sparrow', 0.8)
            """
        )
        con.execute(
            "CREATE VIEW label_summary AS SELECT label, label_name, COUNT(*) AS detections, AVG(confidence) AS avg_confidence FROM detections GROUP BY 1,2"
        )
        con.execute(
            "CREATE VIEW recording_summary AS SELECT recording_id, COUNT(*) AS detections, AVG(confidence) AS avg_confidence FROM detections GROUP BY 1"
        )
        con.execute(
            "CREATE VIEW timeline_summary AS SELECT 0 AS bucket_index, 0 AS bucket_start_ms, COUNT(*) AS detections, AVG(confidence) AS avg_confidence FROM detections"
        )
    finally:
        con.close()
    views = aggregate_api.load_bundle_views(db_path)
    assert not views.label_summary.empty
    assert not views.recording_summary.empty
