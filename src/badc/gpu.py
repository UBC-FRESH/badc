"""GPU detection utilities."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from typing import List


@dataclass
class GPUInfo:
    """Properties reported by ``nvidia-smi`` for a single GPU."""

    index: int
    """Zero-based device index."""

    name: str
    """GPU product name."""

    memory_total_mb: int
    """Total memory capacity (MiB)."""


def detect_gpus() -> List[GPUInfo]:
    """Detect GPUs using ``nvidia-smi`` and return structured metadata.

    Returns
    -------
    list of GPUInfo
        One entry per GPU reported by ``nvidia-smi``. Returns an empty list when
        the command is unavailable or fails.
    """

    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=index,name,memory.total", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return []
    infos: List[GPUInfo] = []
    for line in result.stdout.strip().splitlines():
        if not line:
            continue
        parts = [p.strip() for p in line.split(",")]
        if len(parts) != 3:
            continue
        index = int(parts[0])
        name = parts[1]
        memory_str = parts[2].split()[0]
        try:
            memory_total_mb = int(memory_str)
        except ValueError:
            memory_total_mb = 0
        infos.append(GPUInfo(index=index, name=name, memory_total_mb=memory_total_mb))
    return infos
