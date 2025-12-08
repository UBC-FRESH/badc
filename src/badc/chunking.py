"""Chunk planning helpers plus probe/aggregation logic.

See ``notes/chunking.md`` for the longer-term Plan A (HawkEars-driven probes,
chunk overlap heuristics, manifest hashing, etc.). The functions below stay
lightweight so CLI/tests can exercise the workflow while the more advanced
algorithms are being built.
"""

from __future__ import annotations

import json
import wave
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable, Sequence

from badc.chunk_writer import ChunkMetadata, iter_chunk_metadata
from badc.gpu import GPUDetectionResult, GPUInfo, detect_gpus


@dataclass(frozen=True)
class ChunkProbeAttempt:
    """Single attempt recorded while searching for a safe chunk duration."""

    duration_s: float
    estimated_vram_mb: float
    fits: bool
    reason: str


@dataclass(frozen=True)
class ChunkProbeResult:
    """Represents the outcome of a chunk-size probe run."""

    file: Path
    max_duration_s: float
    strategy: str = "memory_estimator_v1"
    notes: str = ""
    attempts: tuple[ChunkProbeAttempt, ...] = ()
    log_path: Path | None = None


@dataclass(frozen=True)
class _WaveMetadata:
    duration_s: float
    sample_rate: int
    channels: int
    sample_width_bytes: int


def probe_chunk_duration(
    audio_path: Path,
    initial_duration_s: float = 60.0,
    *,
    max_duration_s: float | None = None,
    tolerance_s: float = 5.0,
    gpu_index: int | None = None,
    log_path: Path | None = None,
) -> ChunkProbeResult:
    """Estimate a feasible chunk duration for ``audio_path`` based on GPU VRAM heuristics.

    The function inspects WAV metadata (sample rate, channels, bit depth) and
    approximates the amount of GPU memory each chunk would require. It then
    performs a binary search between ``initial_duration_s`` and ``max_duration_s``
    (or the recording length) until it finds the largest chunk that fits within a
    GPU's memory budget. Each attempt is written to a JSONL telemetry log.
    """

    if initial_duration_s <= 0:
        raise ValueError("initial_duration_s must be positive")
    if tolerance_s <= 0:
        raise ValueError("tolerance_s must be positive")
    if not audio_path.exists():
        raise FileNotFoundError(audio_path)

    metadata = _read_wav_metadata(audio_path)
    if metadata.duration_s <= 0:
        raise RuntimeError(f"{audio_path} has zero duration or unreadable metadata.")
    resolved = audio_path.resolve()
    max_duration = (
        metadata.duration_s if max_duration_s is None else min(max_duration_s, metadata.duration_s)
    )
    max_duration = max(tolerance_s, max_duration)

    detection = detect_gpus()
    gpu_info = _select_gpu(detection, gpu_index)
    memory_limit_mb = _memory_limit_mb(gpu_info, detection)
    notes = _gpu_notes(gpu_info, detection, memory_limit_mb)

    telemetry_path = log_path or _default_probe_log_path(resolved)
    telemetry_path.parent.mkdir(parents=True, exist_ok=True)

    attempts: list[ChunkProbeAttempt] = []

    def record(duration: float, fits: bool, reason: str, estimate_mb: float) -> None:
        attempt = ChunkProbeAttempt(
            duration_s=duration, estimated_vram_mb=estimate_mb, fits=fits, reason=reason
        )
        attempts.append(attempt)
        entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "audio": str(resolved),
            "duration_s": duration,
            "estimated_vram_mb": estimate_mb,
            "fits": fits,
            "reason": reason,
            "gpu_index": gpu_info.index if gpu_info else None,
            "gpu_name": gpu_info.name if gpu_info else None,
            "memory_limit_mb": memory_limit_mb,
        }
        with telemetry_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry) + "\n")

    def evaluate(duration: float) -> tuple[bool, float, str]:
        duration = min(duration, max_duration)
        estimate_mb = _estimate_vram_mb(
            duration,
            metadata.sample_rate,
            metadata.channels,
            metadata.sample_width_bytes,
        )
        if estimate_mb <= memory_limit_mb:
            return True, estimate_mb, "fits memory budget"
        reason = f"Estimated {estimate_mb:.1f} MiB exceeds limit {memory_limit_mb:.1f} MiB"
        return False, estimate_mb, reason

    low_success = 0.0
    high_failure = max_duration
    candidate = min(initial_duration_s, max_duration)
    fits, estimate_mb, reason = evaluate(candidate)
    record(candidate, fits, reason, estimate_mb)
    if fits:
        low_success = candidate
    else:
        high_failure = candidate
        while candidate > tolerance_s:
            candidate = max(tolerance_s, candidate / 2)
            fits, estimate_mb, reason = evaluate(candidate)
            record(candidate, fits, reason, estimate_mb)
            if fits:
                low_success = candidate
                break
            high_failure = candidate
        if low_success == 0.0 and not fits:
            low_success = tolerance_s

    while high_failure - low_success > tolerance_s:
        candidate = (high_failure + low_success) / 2
        fits, estimate_mb, reason = evaluate(candidate)
        record(candidate, fits, reason, estimate_mb)
        if fits:
            low_success = candidate
        else:
            high_failure = candidate

    return ChunkProbeResult(
        file=resolved,
        max_duration_s=round(low_success, 2),
        notes=notes,
        attempts=tuple(attempts),
        log_path=telemetry_path,
    )


def plan_chunk_ranges(duration_s: float, chunk_duration_s: float) -> list[tuple[float, float]]:
    """Return evenly spaced ranges that cover ``duration_s`` seconds."""

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
    """Return mocked detection IDs for each ``chunk_id``."""

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
    chunk_rows: Iterable[ChunkMetadata] | None = None,
) -> Path:
    """Write a chunk manifest CSV (placeholder hashing)."""

    lines = ["recording_id,chunk_id,source_path,start_ms,end_ms,overlap_ms,sha256,notes"]
    recording_id = audio_path.stem
    metadata_iter: Iterable[ChunkMetadata]
    if chunk_rows is not None:
        metadata_iter = chunk_rows
    elif compute_hashes:
        metadata_iter = iter_chunk_metadata(audio_path, chunk_duration_s)
    else:
        metadata_iter = [
            ChunkMetadata(
                chunk_id=f"{recording_id}_{int(start * 1000)}_{int(end * 1000)}",
                path=audio_path,
                start_ms=int(start * 1000),
                end_ms=int(end * 1000),
                overlap_ms=0,
                sha256="TODO_HASH",
            )
            for start, end in plan_chunk_ranges(duration_s, chunk_duration_s)
        ]
    for meta in metadata_iter:
        lines.append(
            ",".join(
                [
                    recording_id,
                    meta.chunk_id,
                    str(meta.path),
                    str(meta.start_ms),
                    str(meta.end_ms),
                    str(meta.overlap_ms),
                    meta.sha256,
                    "",
                ]
            )
        )
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    output_csv.write_text("\n".join(lines) + "\n")
    return output_csv


def _read_wav_metadata(audio_path: Path) -> _WaveMetadata:
    """Return WAV metadata required for chunk-size estimates."""

    try:
        with wave.open(str(audio_path), "rb") as wav_file:
            channels = wav_file.getnchannels()
            sample_width = wav_file.getsampwidth()
            sample_rate = wav_file.getframerate()
            n_frames = wav_file.getnframes()
    except (wave.Error, OSError) as exc:  # pragma: no cover - depends on file format
        raise RuntimeError(f"Failed to read WAV metadata from {audio_path}: {exc}") from exc
    duration = n_frames / sample_rate if sample_rate else 0.0
    return _WaveMetadata(
        duration_s=duration,
        sample_rate=sample_rate,
        channels=channels,
        sample_width_bytes=sample_width,
    )


def _estimate_vram_mb(
    duration_s: float, sample_rate: int, channels: int, sample_width_bytes: int
) -> float:
    """Estimate GPU memory consumption (MiB) for a chunk.

    The heuristic assumes tensors are expanded to float32 during feature
    extraction, so it multiplies by 4 and adds a modest overhead multiplier.
    """

    bytes_per_second = sample_rate * channels * sample_width_bytes
    float_bytes_per_second = bytes_per_second * 4  # upcast to float32
    overhead_factor = 1.35  # convolution/window padding, intermediate tensors
    total_bytes = float_bytes_per_second * duration_s * overhead_factor
    return total_bytes / (1024**2)


def _select_gpu(detection: GPUDetectionResult, preferred_index: int | None) -> GPUInfo | None:
    """Return the GPU we should base estimates on."""

    if not detection.gpus:
        return None
    if preferred_index is not None:
        for info in detection.gpus:
            if info.index == preferred_index:
                return info
    return detection.gpus[0]


def _memory_limit_mb(gpu_info: GPUInfo | None, detection: GPUDetectionResult) -> float:
    """Pick a conservative memory limit in MiB."""

    if gpu_info:
        return max(1.0, gpu_info.memory_total_mb * 0.8)
    # Fallback when detection fails (dev server default).
    return 4096.0 if detection.diagnostic else 4096.0


def _gpu_notes(gpu_info: GPUInfo | None, detection: GPUDetectionResult, limit_mb: float) -> str:
    """Return a human-readable note about the GPU limit used."""

    if gpu_info:
        return f"GPU {gpu_info.index} ({gpu_info.name}) limit {limit_mb:.0f} MiB"
    if detection.diagnostic:
        return f"Assumed 4 GiB limit (GPU detection failed: {detection.diagnostic})"
    return "Assumed 4 GiB limit (no GPUs detected)"


def _default_probe_log_path(audio_path: Path) -> Path:
    """Return the default telemetry path for probe attempts."""

    slug = audio_path.stem.replace(" ", "_")
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return Path("artifacts") / "telemetry" / "chunk_probe" / f"{slug}_{timestamp}.jsonl"
