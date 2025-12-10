from __future__ import annotations

import wave
from pathlib import Path

import numpy as np
import pytest

from badc.chunk_writer import ChunkMetadata, iter_chunk_metadata


def _write_wav(path: Path, duration_s: float, sample_rate: int = 8000) -> None:
    frames = int(duration_s * sample_rate)
    values = bytes([0] * frames * 2)  # mono 16-bit
    with wave.open(str(path), "wb") as fh:
        fh.setnchannels(1)
        fh.setsampwidth(2)
        fh.setframerate(sample_rate)
        fh.writeframes(values)


def test_iter_chunk_metadata_wav(tmp_path: Path) -> None:
    source = tmp_path / "audio.wav"
    _write_wav(source, duration_s=1.0)
    chunks = list(
        iter_chunk_metadata(
            source, chunk_duration_s=0.25, overlap_s=0.0, output_dir=tmp_path / "chunks"
        )
    )
    assert chunks
    for meta in chunks:
        assert isinstance(meta, ChunkMetadata)
        assert meta.path.exists()
        assert meta.path.suffix == ".wav"
        assert meta.sha256


def test_iter_chunk_metadata_flac(tmp_path: Path) -> None:
    sf = pytest.importorskip("soundfile")
    data = np.linspace(-0.5, 0.5, num=8000).astype("float32")
    source = tmp_path / "audio.flac"
    sf.write(str(source), data, samplerate=8000, format="FLAC")
    chunks = list(
        iter_chunk_metadata(
            source, chunk_duration_s=0.25, overlap_s=0.0, output_dir=tmp_path / "chunks_flac"
        )
    )
    assert chunks
    for meta in chunks:
        assert meta.path.exists()
        assert meta.path.suffix == ".wav"
        assert meta.sha256
