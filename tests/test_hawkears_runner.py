from __future__ import annotations

from pathlib import Path

from badc.hawkears_runner import _parse_hawkears_labels
from badc.infer_scheduler import InferenceJob


def make_job(tmp_path: Path) -> InferenceJob:
    chunk_path = tmp_path / "chunk.wav"
    chunk_path.write_text("stub")
    return InferenceJob(chunk_id="chunk_a", chunk_path=chunk_path, recording_id="rec1")


def test_parse_hawkears_labels_filters_filenames(tmp_path: Path) -> None:
    csv_path = tmp_path / "HawkEars_labels.csv"
    csv_path.write_text(
        "filename,start_time,end_time,class_name,class_code,score\n"
        "chunk.wav,0.5,1.5,Ruffed Grouse,RUGR,0.87\n"
        "other.wav,0.0,1.0,Other,OTHR,0.5\n"
    )
    job = make_job(tmp_path)
    payload = _parse_hawkears_labels(csv_path, job)
    assert payload["status"] == "ok"
    assert len(payload["detections"]) == 1
    detection = payload["detections"][0]
    assert detection["label"] == "RUGR"
    assert detection["timestamp_ms"] == 500
    assert detection["end_ms"] == 1500
    assert detection["confidence"] == 0.87


def test_parse_hawkears_labels_handles_missing_file(tmp_path: Path) -> None:
    csv_path = tmp_path / "missing.csv"
    job = make_job(tmp_path)
    payload = _parse_hawkears_labels(csv_path, job)
    assert payload["status"] == "no_output"
    assert payload["detections"] == []
