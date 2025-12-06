"""Chunking utilities and placeholder probe logic."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

from badc.audio import compute_sha256


@dataclass(frozen=True)
class ChunkProbeResult:
    """Represents the outcome of a chunk-size probe run."""

    file: Path
    max_duration_s: float
    strategy: str = "placeholder"
    notes: str = ""


def probe_chunk_duration(audio_path: Path, initial_duration_s: float = 60.0) -> ChunkProbeResult:
    """Return a placeholder probe result for the given audio file.

    Parameters
    ----------
    audio_path:
        Path to the audio file under test.
    initial_duration_s:
        Starting duration (seconds) for the probe routine.
    """

    if initial_duration_s <= 0:
        raise ValueError("initial_duration_s must be positive")
    if not audio_path.exists():
        raise FileNotFoundError(audio_path)
    resolved = audio_path.resolve()
    return ChunkProbeResult(
        file=resolved,
        max_duration_s=initial_duration_s,
        notes="Probe stub — replace with HawkEars-powered binary search",
    )


def plan_chunk_ranges(duration_s: float, chunk_duration_s: float) -> list[tuple[float, float]]:
    """Return evenly spaced chunk ranges for the requested duration.

    Parameters
    ----------
    duration_s:
        Total length of the source audio (seconds).
    chunk_duration_s:
        Desired chunk size (seconds).
    """

    if chunk_duration_s <= 0:
        raise ValueError("chunk_duration_s must be positive")
    ranges: list[tuple[float, float]] = []
    start = 0.0
    while start < duration_s:
        end = min(start + chunk_duration_s, duration_s)
        ranges.append((start, end))
        start = end
    return ranges


def iter_chunk_placeholders(audio_path: Path, chunk_duration_s: float) -> Iterable[str]:
    """Yield placeholder chunk identifiers for documentation/testing."""

    fake_duration = chunk_duration_s * 3
    for start, end in plan_chunk_ranges(fake_duration, chunk_duration_s):
        yield f"{audio_path.stem}_{int(start)}_{int(end)}"


def run_inference_on_chunks(chunk_ids: Sequence[str]) -> list[str]:
    """Placeholder inference runner; returns mocked detection IDs."""

    return [f"{chunk_id}_detected" for chunk_id in chunk_ids]


def aggregate_detections(detections: Sequence[str]) -> dict[str, int]:
    """Aggregate placeholder detections by chunk prefix."""

    summary: dict[str, int] = {}
    for det in detections:
        chunk_name = det.split("_detected")[0]
        summary[chunk_name] = summary.get(chunk_name, 0) + 1
    return summary


def write_manifest(
    audio_path: Path,
    chunk_duration_s: float,
    output_csv: Path,
    duration_s: float,
    compute_hashes: bool = False,
) -> Path:
    """Write a chunk manifest CSV (placeholder hashing)."""

    ranges = plan_chunk_ranges(duration_s, chunk_duration_s)
    lines = ["recording_id,chunk_id,source_path,start_ms,end_ms,overlap_ms,sha256,notes"]
    recording_id = audio_path.stem
    base_hash = compute_sha256(audio_path) if compute_hashes else "TODO_HASH"
    for start, end in ranges:
        chunk_id = f"{recording_id}_{int(start * 1000)}_{int(end * 1000)}"
        sha256 = base_hash if compute_hashes else "TODO_HASH"
        lines.append(
            ",".join(
                [
                    recording_id,
                    chunk_id,
                    str(audio_path),
                    str(int(start * 1000)),
                    str(int(end * 1000)),
                    "0",
                    sha256,
                    "",
                ]
            )
        )
    output_csv.write_text("\n".join(lines) + "\n")
    return output_csv
