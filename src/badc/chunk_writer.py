"""Chunk file writer implementation."""

from __future__ import annotations

import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from badc.audio import compute_sha256


@dataclass
class ChunkMetadata:
    chunk_id: str
    path: Path
    start_ms: int
    end_ms: int
    overlap_ms: int
    sha256: str


def iter_chunk_metadata(
    audio_path: Path,
    chunk_duration_s: float,
    overlap_s: float = 0,
    output_dir: Path | None = None,
) -> Iterator[ChunkMetadata]:
    if chunk_duration_s <= 0:
        raise ValueError("chunk_duration_s must be positive")
    if overlap_s < 0:
        raise ValueError("overlap_s cannot be negative")
    if not audio_path.exists():
        raise FileNotFoundError(audio_path)

    output_dir = output_dir or Path("artifacts") / "chunks" / audio_path.stem
    output_dir.mkdir(parents=True, exist_ok=True)

    with wave.open(str(audio_path), "rb") as src:
        sample_rate = src.getframerate()
        sample_width = src.getsampwidth()
        channels = src.getnchannels()
        total_frames = src.getnframes()
        chunk_frames = max(int(chunk_duration_s * sample_rate), 1)
        overlap_frames = max(int(overlap_s * sample_rate), 0)
        start_frame = 0
        overlap_ms = int(overlap_frames / sample_rate * 1000)
        while start_frame < total_frames:
            end_frame = min(start_frame + chunk_frames, total_frames)
            src.setpos(start_frame)
            frames = src.readframes(end_frame - start_frame)
            start_ms = int(start_frame / sample_rate * 1000)
            end_ms = int(end_frame / sample_rate * 1000)
            chunk_id = f"{audio_path.stem}_chunk_{start_ms}_{end_ms}"
            chunk_path = output_dir / f"{chunk_id}.wav"
            with wave.open(str(chunk_path), "wb") as dst:
                dst.setnchannels(channels)
                dst.setsampwidth(sample_width)
                dst.setframerate(sample_rate)
                dst.writeframes(frames)
            sha256 = compute_sha256(chunk_path)
            yield ChunkMetadata(
                chunk_id=chunk_id,
                path=chunk_path,
                start_ms=start_ms,
                end_ms=end_ms,
                overlap_ms=overlap_ms,
                sha256=sha256,
            )
            start_frame = (
                end_frame
                if chunk_frames <= overlap_frames
                else start_frame + chunk_frames - overlap_frames
            )
