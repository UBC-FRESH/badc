"""Planning helpers for dataset-wide chunking orchestration (Phase 2)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ChunkPlan:
    """Plan describing how to chunk a single recording."""

    audio_path: Path
    manifest_path: Path
    chunk_output_dir: Path
    chunk_duration: float
    overlap: float

    @property
    def recording_id(self) -> str:
        return self.audio_path.stem


def _resolve(base: Path, value: Path) -> Path:
    return value if value.is_absolute() else (base / value)


def build_chunk_plan(
    dataset_root: Path,
    *,
    pattern: str = "*.wav",
    chunk_duration: float = 60.0,
    overlap: float = 0.0,
    manifest_dir: Path = Path("manifests"),
    chunks_dir: Path = Path("artifacts/chunks"),
    include_existing: bool = False,
    limit: int | None = None,
) -> list[ChunkPlan]:
    """Return chunk plans for WAV files under ``dataset_root/audio``.

    Parameters
    ----------
    dataset_root
        Path to a DataLad dataset containing ``audio/`` recordings.
    pattern
        Glob used to select source audio files (defaults to ``*.wav``).
    chunk_duration
        Target chunk duration in seconds.
    overlap
        Overlap between consecutive chunks in seconds.
    manifest_dir
        Directory where manifest CSVs should be written (relative to dataset root unless absolute).
    chunks_dir
        Directory that will hold chunk WAVs (relative to dataset root unless absolute).
    include_existing
        When ``False`` (default), recordings whose manifest already exists are skipped.
    limit
        Optional cap on the number of plans to return.
    """

    dataset_root = dataset_root.expanduser().resolve()
    audio_root = dataset_root / "audio"
    if not audio_root.exists():
        raise FileNotFoundError(f"Audio directory not found at {audio_root}")
    manifest_root = _resolve(dataset_root, manifest_dir)
    chunks_root = _resolve(dataset_root, chunks_dir)
    plans: list[ChunkPlan] = []
    for audio_path in sorted(audio_root.rglob(pattern)):
        if not audio_path.is_file():
            continue
        recording_id = audio_path.stem
        manifest_path = manifest_root / f"{recording_id}.csv"
        if not include_existing and manifest_path.exists():
            continue
        chunk_output_dir = chunks_root / recording_id
        plans.append(
            ChunkPlan(
                audio_path=audio_path,
                manifest_path=manifest_path,
                chunk_output_dir=chunk_output_dir,
                chunk_duration=chunk_duration,
                overlap=overlap,
            )
        )
        if limit and len(plans) >= limit:
            break
    return plans


def render_datalad_run(plan: ChunkPlan, dataset_root: Path) -> str:
    """Return a ready-to-run ``datalad run`` command for the provided plan."""

    dataset_root = dataset_root.expanduser().resolve()
    audio_abs = plan.audio_path.resolve()
    manifest_abs = plan.manifest_path.resolve(strict=False)
    chunks_abs = plan.chunk_output_dir.resolve(strict=False)
    try:
        audio_rel = audio_abs.relative_to(dataset_root)
        manifest_rel = manifest_abs.relative_to(dataset_root)
        chunks_rel = chunks_abs.relative_to(dataset_root)
    except ValueError as exc:  # pragma: no cover - defensive
        raise ValueError("Plan paths must live inside the dataset root.") from exc

    return (
        f'datalad run -m "Chunk {plan.recording_id}" '
        f"--input {audio_rel} "
        f"--output {chunks_rel} "
        f"--output {manifest_rel} "
        f"-- badc chunk run {audio_rel} "
        f"--chunk-duration {plan.chunk_duration} "
        f"--overlap {plan.overlap} "
        f"--output-dir {chunks_rel} "
        f"--manifest {manifest_rel}"
    )
