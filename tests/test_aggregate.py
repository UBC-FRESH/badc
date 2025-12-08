from __future__ import annotations

import json
from pathlib import Path

import pytest

from badc.aggregate import (
    DetectionRecord,
    load_detections,
    summarize_parquet,
    write_parquet,
    write_summary_csv,
)


def test_load_detections_with_chunk_metadata(tmp_path: Path) -> None:
    detections_dir = tmp_path / "artifacts" / "infer" / "rec1"
    detections_dir.mkdir(parents=True)
    payload = {
        "chunk_id": "chunk_a",
        "recording_id": "rec1",
        "source_path": str(detections_dir / "chunk_a.json"),
        "status": "ok",
        "chunk": {
            "start_ms": 1000,
            "end_ms": 2000,
            "sha256": "abc123",
        },
        "runner": "hawkears",
        "dataset_root": str(tmp_path),
        "model_version": "HawkEars-1.2.3",
        "detections": [
            {
                "timestamp_ms": 500,
                "end_ms": 900,
                "label": "RUGR",
                "label_code": "RUGR",
                "label_name": "Ruffed Grouse",
                "confidence": 0.9,
            },
        ],
    }
    (detections_dir / "chunk_a.json").write_text(json.dumps(payload))
    records = load_detections(tmp_path / "artifacts" / "infer")
    assert len(records) == 1
    rec = records[0]
    assert rec.absolute_time_ms == 1500
    assert rec.chunk_sha256 == "abc123"
    assert rec.detection_end_ms == 900
    assert rec.absolute_end_ms == 1900
    assert rec.label_code == "RUGR"
    assert rec.label_name == "Ruffed Grouse"
    assert rec.model_version == "HawkEars-1.2.3"


def test_load_detections_uses_manifest_metadata(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.csv"
    dataset_root = tmp_path / "dataset"
    (dataset_root / ".datalad").mkdir(parents=True)
    chunk_path = dataset_root / "audio" / "chunk_a.wav"
    chunk_path.parent.mkdir(parents=True)
    chunk_path.write_text("audio", encoding="utf-8")
    manifest.write_text(
        "recording_id,chunk_id,source_path,start_ms,end_ms,overlap_ms,sha256,notes\n"
        f"rec_manifest,chunk_a,{chunk_path},123,456,0,sha999,\n",
        encoding="utf-8",
    )
    detections_dir = tmp_path / "artifacts" / "infer" / "placeholder"
    detections_dir.mkdir(parents=True)
    payload = {
        "chunk_id": "chunk_a",
        "status": "ok",
        "detections": [{"timestamp_ms": 5, "label": "grouse", "confidence": 0.9}],
    }
    (detections_dir / "chunk_a.json").write_text(json.dumps(payload))
    records = load_detections(tmp_path / "artifacts" / "infer", manifest=manifest)
    assert len(records) == 1
    rec = records[0]
    assert rec.recording_id == "rec_manifest"
    assert rec.chunk_start_ms == 123
    assert rec.chunk_end_ms == 456
    assert rec.chunk_sha256 == "sha999"
    assert rec.source_path == chunk_path
    assert rec.dataset_root == dataset_root


def test_write_summary_and_parquet(tmp_path: Path) -> None:
    records = [
        DetectionRecord(
            recording_id="rec1",
            chunk_id="chunk_a",
            chunk_start_ms=0,
            chunk_end_ms=1000,
            timestamp_ms=100,
            absolute_time_ms=100,
            detection_end_ms=200,
            absolute_end_ms=300,
            label="grouse",
            label_code="RUGR",
            label_name="Ruffed Grouse",
            confidence=0.8,
            status="ok",
            runner="hawkears",
            model_version="HawkEars-1.2.3",
            chunk_sha256="abc123",
            source_path=tmp_path / "chunk_a.json",
            dataset_root=tmp_path,
        )
    ]
    csv_path = write_summary_csv(records, tmp_path / "summary.csv")
    assert csv_path.exists()
    header, row = csv_path.read_text().strip().splitlines()
    assert "label_code" in header
    assert "model_version" in header
    assert "RUGR" in row
    duckdb = pytest.importorskip("duckdb")
    parquet_path = write_parquet(records, tmp_path / "detections.parquet")
    assert parquet_path.exists()
    con = duckdb.connect()
    rows = con.execute(f"SELECT * FROM '{parquet_path}'").fetchall()
    assert len(rows) == 1
    assert len(rows[0]) == 18
    con.close()


def test_summarize_parquet_group_by_label(tmp_path: Path) -> None:
    pytest.importorskip("duckdb")
    records = [
        DetectionRecord(
            recording_id="rec1",
            chunk_id="chunk_a",
            chunk_start_ms=0,
            chunk_end_ms=1000,
            timestamp_ms=100,
            absolute_time_ms=100,
            label="grouse",
            confidence=0.9,
            status="ok",
            runner="hawkears",
            chunk_sha256="abc123",
            source_path=tmp_path / "chunk_a.json",
            dataset_root=tmp_path,
        ),
        DetectionRecord(
            recording_id="rec2",
            chunk_id="chunk_b",
            chunk_start_ms=0,
            chunk_end_ms=1000,
            timestamp_ms=200,
            absolute_time_ms=200,
            label="grouse",
            confidence=0.7,
            status="ok",
            runner="hawkears",
            chunk_sha256="def456",
            source_path=tmp_path / "chunk_b.json",
            dataset_root=tmp_path,
        ),
    ]
    parquet_path = write_parquet(records, tmp_path / "detections.parquet")
    rows = summarize_parquet(parquet_path, group_by=["label"])
    assert len(rows) == 1
    label, count, avg_conf = rows[0]
    assert label == "grouse"
    assert count == 2
    assert avg_conf == pytest.approx(0.8)


def test_summarize_parquet_rejects_unknown_column(tmp_path: Path) -> None:
    pytest.importorskip("duckdb")
    records = [
        DetectionRecord(
            recording_id="rec1",
            chunk_id="chunk_a",
            chunk_start_ms=0,
            chunk_end_ms=1000,
            timestamp_ms=0,
            absolute_time_ms=0,
            label="grouse",
            confidence=0.5,
            status="ok",
            runner="hawkears",
            chunk_sha256="abc123",
            source_path=tmp_path / "chunk_a.json",
            dataset_root=tmp_path,
        )
    ]
    parquet_path = write_parquet(records, tmp_path / "detections.parquet")
    with pytest.raises(ValueError):
        summarize_parquet(parquet_path, group_by=["unknown"])


def test_quicklook_metrics_returns_expected_tables(tmp_path: Path) -> None:
    pytest.importorskip("duckdb")
    records = [
        DetectionRecord(
            recording_id="rec1",
            chunk_id="chunk_a",
            chunk_start_ms=0,
            chunk_end_ms=30000,
            timestamp_ms=100,
            absolute_time_ms=100,
            label="WTSP",
            label_name="White-throated Sparrow",
            confidence=0.9,
            status="ok",
            runner="hawkears",
            chunk_sha256="chunk_a_sha",
            source_path=tmp_path / "chunk_a.json",
            dataset_root=tmp_path,
        ),
        DetectionRecord(
            recording_id="rec2",
            chunk_id="chunk_b",
            chunk_start_ms=30000,
            chunk_end_ms=60000,
            timestamp_ms=200,
            absolute_time_ms=30200,
            label="BAWW",
            label_name="Black-and-white Warbler",
            confidence=0.8,
            status="ok",
            runner="hawkears",
            chunk_sha256="chunk_b_sha",
            source_path=tmp_path / "chunk_b.json",
            dataset_root=tmp_path,
        ),
        DetectionRecord(
            recording_id="rec1",
            chunk_id="chunk_b",
            chunk_start_ms=30000,
            chunk_end_ms=60000,
            timestamp_ms=500,
            absolute_time_ms=30500,
            label="WTSP",
            label_name="White-throated Sparrow",
            confidence=0.95,
            status="ok",
            runner="hawkears",
            chunk_sha256="chunk_b_sha",
            source_path=tmp_path / "chunk_b.json",
            dataset_root=tmp_path,
        ),
    ]
    parquet_path = write_parquet(records, tmp_path / "detections.parquet")
    from badc.aggregate import quicklook_metrics

    quicklook = quicklook_metrics(parquet_path, top_labels=5, top_recordings=5)
    assert quicklook.top_labels[0][0] == "WTSP"
    assert quicklook.top_labels[0][2] == 2
    assert quicklook.top_recordings[0][0] == "rec1"
    assert quicklook.chunk_timeline[0][0] == "chunk_a"
    assert quicklook.chunk_timeline[-1][0] == "chunk_b"
