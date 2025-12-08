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


@dataclass
class GPUMetrics:
    """Snapshot of GPU utilization and memory usage."""

    index: int
    utilization: int | None
    memory_used_mb: int | None
    memory_total_mb: int | None


@dataclass
class GPUDetectionResult:
    """Structured output from :func:`detect_gpus`."""

    gpus: List[GPUInfo]
    """List of detected GPUs (empty when detection fails)."""

    diagnostic: str | None = None
    """Human-readable explanation when detection fails."""


def _diagnostic_from_error(message: str | None, exception: Exception | None = None) -> str:
    """Return a friendly diagnostic string for GPU detection failures."""

    msg = (message or "").strip()
    if "Insufficient Permissions" in msg:
        return (
            "nvidia-smi reported 'Insufficient Permissions'. GPU inventory usually requires "
            "NVML access—try running `sudo nvidia-smi` to confirm the driver works or ask the "
            "cluster admin to grant your user access to the NVIDIA devices."
        )
    if msg:
        return msg
    if exception:
        return f"Failed to run nvidia-smi: {exception}"
    return "Failed to run nvidia-smi (unknown error)."


def detect_gpus() -> GPUDetectionResult:
    """Detect GPUs using ``nvidia-smi`` and return structured metadata.

    Returns
    -------
    GPUDetectionResult
        The inventory plus an optional diagnostic message describing why detection failed.
    """

    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=index,name,memory.total", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            check=True,
        )
    except FileNotFoundError:
        diagnostic = (
            "nvidia-smi is not available on PATH. Install the NVIDIA drivers or ensure "
            "CUDA utilities are accessible."
        )
        return GPUDetectionResult(gpus=[], diagnostic=diagnostic)
    except subprocess.CalledProcessError as exc:
        diagnostic = _diagnostic_from_error(exc.stderr, exc)
        return GPUDetectionResult(gpus=[], diagnostic=diagnostic)
    except OSError as exc:
        diagnostic = _diagnostic_from_error(None, exc)
        return GPUDetectionResult(gpus=[], diagnostic=diagnostic)

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
    return GPUDetectionResult(gpus=infos)


def query_gpu_metrics(index: int) -> GPUMetrics | None:
    """Return utilization + memory stats for ``index`` via ``nvidia-smi``."""

    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                f"--id={index}",
                "--query-gpu=utilization.gpu,memory.used,memory.total",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError, OSError):
        return None
    line = result.stdout.strip().splitlines()
    if not line:
        return None
    parts = [p.strip() for p in line[0].split(",")]
    if len(parts) != 3:
        return None
    try:
        util = int(parts[0])
    except ValueError:
        util = None
    try:
        mem_used = int(parts[1])
    except ValueError:
        mem_used = None
    try:
        mem_total = int(parts[2])
    except ValueError:
        mem_total = None
    return GPUMetrics(
        index=index,
        utilization=util,
        memory_used_mb=mem_used,
        memory_total_mb=mem_total,
    )
