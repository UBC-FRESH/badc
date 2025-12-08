from __future__ import annotations

from badc import gpu


def test_query_gpu_metrics_parses(monkeypatch) -> None:
    class Result:
        stdout = "25, 512, 8192\n"

    monkeypatch.setattr(
        gpu.subprocess,
        "run",
        lambda *args, **kwargs: Result(),
    )
    metrics = gpu.query_gpu_metrics(0)
    assert metrics is not None
    assert metrics.utilization == 25
    assert metrics.memory_used_mb == 512


def test_query_gpu_metrics_handles_failure(monkeypatch) -> None:
    def raise_error(*args, **kwargs):
        raise gpu.subprocess.CalledProcessError(1, args[0])

    monkeypatch.setattr(gpu.subprocess, "run", raise_error)
    assert gpu.query_gpu_metrics(0) is None
