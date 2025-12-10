from __future__ import annotations

import sys
from pathlib import Path

import pytest

from badc.hawkears_runner import JobExecutionError, _parse_hawkears_labels, run_job
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
    payload = _parse_hawkears_labels(
        csv_path, job, dataset_root=None, runner="hawkears", model_version="hawkears-main"
    )
    assert payload["status"] == "ok"
    assert len(payload["detections"]) == 1
    detection = payload["detections"][0]
    assert detection["label"] == "RUGR"
    assert detection["timestamp_ms"] == 500
    assert detection["end_ms"] == 1500
    assert detection["confidence"] == 0.87
    assert detection["label_code"] == "RUGR"
    assert detection["label_name"] == "Ruffed Grouse"
    assert payload["model_version"] == "hawkears-main"


def test_parse_hawkears_labels_handles_missing_file(tmp_path: Path) -> None:
    csv_path = tmp_path / "missing.csv"
    job = make_job(tmp_path)
    payload = _parse_hawkears_labels(csv_path, job, dataset_root=None, runner="hawkears")
    assert payload["status"] == "no_output"
    assert payload["detections"] == []


def test_run_job_reports_backoff_metadata(tmp_path: Path) -> None:
    job = make_job(tmp_path)
    output_dir = tmp_path / "outputs"
    output_dir.mkdir()
    telemetry = tmp_path / "telemetry.jsonl"
    fail_script = tmp_path / "fail.py"
    fail_script.write_text("import sys; sys.exit(1)")
    with pytest.raises(JobExecutionError) as excinfo:
        run_job(
            job=job,
            worker=None,
            output_dir=output_dir,
            runner_cmd=f"{sys.executable} {fail_script}",
            max_retries=0,
            use_hawkears=False,
            hawkears_args=None,
            dataset_root=None,
            telemetry_path=telemetry,
        )
    err = excinfo.value
    assert err.last_backoff_s is not None
    assert err.last_error
