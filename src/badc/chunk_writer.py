"""Chunk writer utilities used by CLI and batch workflows.

`badc chunk run` and related notebooks import this module to turn long recordings
into evenly sized WAV snippets plus metadata that downstream inference and
telemetry consumers rely on. See ``notes/chunking.md`` for broader context.
"""

from __future__ import annotations

import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from badc.audio import compute_sha256


@dataclass
class ChunkMetadata:
    """Metadata describing a chunk produced by ``iter_chunk_metadata``."""

    chunk_id: str
    """Identifier derived from the source stem and time bounds."""

    path: Path
    """Filesystem path to the chunk WAV."""

    start_ms: int
    """Chunk start offset in milliseconds from the source origin."""

    end_ms: int
    """Chunk end offset in milliseconds from the source origin."""

    overlap_ms: int
    """Overlap applied to the chunk in milliseconds (0 when none)."""

    sha256: str
    """SHA256 checksum of the emitted WAV (hex)."""


def iter_chunk_metadata(
    audio_path: Path,
    chunk_duration_s: float,
    overlap_s: float = 0,
    output_dir: Path | None = None,
) -> Iterator[ChunkMetadata]:
    """Generate chunk WAVs and metadata for a single audio file.

    Parameters
    ----------
    audio_path
        Path to the source WAV file (must exist).
    chunk_duration_s
        Target duration for each chunk in seconds (strictly positive).
    overlap_s
        Optional overlap between chunks in seconds. Defaults to ``0``.
    output_dir
        Directory used to store chunk WAVs. When ``None``, files are written
        under ``artifacts/chunks/<stem>`` relative to the current working tree.

    Yields
    ------
    ChunkMetadata
        Dataclass describing the chunk identifier, offsets, overlap, and hash.

    Raises
    ------
    ValueError
        If ``chunk_duration_s`` <= 0 or ``overlap_s`` < 0.
    FileNotFoundError
        If ``audio_path`` does not exist.

    Notes
    -----
    Each iteration writes the chunk WAV to disk before yielding the metadata, so
    consumers should expect filesystem side effects as they traverse the
    generator.
    """
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
