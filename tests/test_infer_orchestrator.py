from __future__ import annotations

from pathlib import Path

from badc.infer_orchestrator import (
    InferPlan,
    build_infer_plan,
    load_manifest_paths_from_plan,
    render_datalad_run,
)


def test_build_infer_plan_skips_existing(tmp_path: Path) -> None:
    dataset = tmp_path / "dataset"
    manifest_dir = dataset / "manifests"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    manifest1 = manifest_dir / "rec1.csv"
    manifest2 = manifest_dir / "rec2.csv"
    manifest1.write_text(
        "recording_id,chunk_id,source_path,start_ms,end_ms,overlap_ms,sha256,notes\n"
    )
    manifest2.write_text(
        "recording_id,chunk_id,source_path,start_ms,end_ms,overlap_ms,sha256,notes\n"
    )
    output_dir = dataset / "artifacts" / "infer" / "rec1"
    output_dir.mkdir(parents=True, exist_ok=True)

    plans = build_infer_plan(
        dataset,
        include_existing=False,
        max_gpus=1,
        hawkears_args=["--min_score", "0.8"],
    )
    assert [plan.recording_id for plan in plans] == ["rec2"]
    plan = plans[0]
    assert plan.max_gpus == 1
    assert plan.hawkears_args == ("--min_score", "0.8")


def test_render_datalad_run(tmp_path: Path) -> None:
    dataset = tmp_path / "dataset"
    dataset.mkdir()
    plan = InferPlan(
        manifest_path=dataset / "manifests" / "rec.csv",
        output_dir=dataset / "artifacts" / "infer" / "rec",
        telemetry_log=dataset / "artifacts" / "telemetry" / "rec.jsonl",
        use_hawkears=True,
        hawkears_args=("--min_score", "0.7"),
        max_gpus=1,
    )
    plan.manifest_path.parent.mkdir(parents=True, exist_ok=True)
    plan.manifest_path.write_text("")
    command = render_datalad_run(plan, dataset)
    assert "--max-gpus 1" in command
    assert "--hawkears-arg --min_score" in command


def test_render_datalad_run_with_resume(tmp_path: Path) -> None:
    dataset = tmp_path / "dataset"
    dataset.mkdir()
    plan = InferPlan(
        manifest_path=dataset / "manifests" / "rec.csv",
        output_dir=dataset / "artifacts" / "infer",
        telemetry_log=dataset / "artifacts" / "telemetry" / "rec.jsonl",
    )
    plan.manifest_path.parent.mkdir(parents=True, exist_ok=True)
    plan.manifest_path.write_text("")
    summary = dataset / "artifacts" / "telemetry" / "rec.summary.json"
    summary.parent.mkdir(parents=True, exist_ok=True)
    summary.write_text("{}", encoding="utf-8")
    command = render_datalad_run(plan, dataset, resume_summary=summary)
    assert "--resume-summary artifacts/telemetry/rec.summary.json" in command


def test_load_manifest_paths_from_plan(tmp_path: Path) -> None:
    csv_plan = tmp_path / "plan.csv"
    csv_plan.write_text("manifest_path\nfoo.csv\n")
    assert load_manifest_paths_from_plan(csv_plan) == [Path("foo.csv")]
    json_plan = tmp_path / "plan.json"
    json_plan.write_text('[{"manifest_path": "bar.csv"}]')
    assert load_manifest_paths_from_plan(json_plan) == [Path("bar.csv")]
