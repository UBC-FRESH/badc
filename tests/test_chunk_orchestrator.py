from __future__ import annotations

from pathlib import Path

from badc.chunk_orchestrator import ChunkPlan, build_chunk_plan, render_datalad_run


def _touch_audio(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\x00\x00")


def test_build_chunk_plan_skips_existing(tmp_path: Path) -> None:
    dataset = tmp_path / "dataset"
    audio_dir = dataset / "audio"
    _touch_audio(audio_dir / "rec1.wav")
    _touch_audio(audio_dir / "rec2.wav")
    manifest_dir = dataset / "manifests"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    (manifest_dir / "rec1.csv").write_text("stub")

    plans = build_chunk_plan(dataset, include_existing=False, chunk_duration=42.0, overlap=1.5)
    assert [plan.recording_id for plan in plans] == ["rec2"]
    plan = plans[0]
    assert plan.chunk_duration == 42.0
    assert plan.overlap == 1.5
    assert plan.manifest_path.name == "rec2.csv"
    assert plan.chunk_output_dir.name == "rec2"


def test_render_datalad_run(tmp_path: Path) -> None:
    dataset = tmp_path / "dataset"
    dataset.mkdir()
    plan = ChunkPlan(
        audio_path=dataset / "audio" / "rec.wav",
        manifest_path=dataset / "manifests" / "rec.csv",
        chunk_output_dir=dataset / "artifacts" / "chunks" / "rec",
        chunk_duration=30.0,
        overlap=2.0,
    )
    plan.audio_path.parent.mkdir(parents=True, exist_ok=True)
    plan.audio_path.write_bytes(b"\x00")
    command = render_datalad_run(plan, dataset)
    expected = (
        'datalad run -m "Chunk rec" '
        "--input audio/rec.wav "
        "--output artifacts/chunks/rec "
        "--output manifests/rec.csv "
        "-- badc chunk run audio/rec.wav "
        "--chunk-duration 30.0 "
        "--overlap 2.0 "
        "--output-dir artifacts/chunks/rec "
        "--manifest manifests/rec.csv"
    )
    assert command == expected
