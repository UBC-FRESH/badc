from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from badc.aggregate import DetectionRecord, write_parquet
from badc.cli.main import app

runner = CliRunner()


def _make_records(tmp_path: Path) -> list[DetectionRecord]:
    chunk_path = tmp_path / "chunk.wav"
    chunk_path.write_text("audio", encoding="utf-8")
    return [
        DetectionRecord(
            recording_id="rec1",
            chunk_id="rec1_chunk_0_1000",
            label="WTSP",
            status="ok",
            source_path=chunk_path,
            confidence=0.9,
            chunk_start_ms=0,
            chunk_end_ms=1000,
        ),
        DetectionRecord(
            recording_id="rec1",
            chunk_id="rec1_chunk_1000_2000",
            label="RUGR",
            status="ok",
            source_path=chunk_path,
            confidence=0.8,
            chunk_start_ms=1000,
            chunk_end_ms=2000,
        ),
        DetectionRecord(
            recording_id="rec2",
            chunk_id="rec2_chunk_0_1000",
            label="WTSP",
            status="ok",
            source_path=chunk_path,
            confidence=0.95,
            chunk_start_ms=0,
            chunk_end_ms=1000,
        ),
    ]


def test_report_parquet_cli(tmp_path: Path) -> None:
    pytest.importorskip("duckdb")
    parquet_path = tmp_path / "detections.parquet"
    records = _make_records(tmp_path)
    write_parquet(records, parquet_path)
    output_dir = tmp_path / "report"
    result = runner.invoke(
        app,
        [
            "report",
            "parquet",
            "--parquet",
            str(parquet_path),
            "--bucket-minutes",
            "1",
            "--output-dir",
            str(output_dir),
        ],
    )
    assert result.exit_code == 0, result.stdout
    assert (output_dir / "labels.csv").exists()
    assert (output_dir / "recordings.csv").exists()
    assert (output_dir / "timeline.csv").exists()
    assert (output_dir / "summary.json").exists()
