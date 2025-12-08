# GPU Monitoring & Profiling Plan

We need to confirm HawkEars consumes available CUDA capacity across environments (dev server = 2×
NVIDIA Quadro RTX 4000; Sockeye GPU nodes = up to 4× GPUs per job). This note captures the tools
and automation we will use to monitor/record GPU utilization.

## Goals
1. Real-time visibility: watch memory, SM occupancy, temperature, and power draw while running
   HawkEars locally and on Sockeye.
2. Historical telemetry: capture per-chunk logs (timestamped) so we can correlate throughput with
   GPU usage in post-hoc analyses.
3. Deployment parity: scripts/CLI flags must adapt to variable GPU counts (2 vs. 4) and gracefully
   handle single-GPU fallbacks.

## Candidate tooling
- `nvidia-smi --query-gpu=timestamp,index,name,utilization.gpu,utilization.memory,memory.used --format=csv`: baseline sampling every N seconds (pipe into CSV for archival).
- `nvidia-smi dmon`: lightweight daemon-like monitor for real-time CLI output.
- `nvtop` (interactive) for local debugging sessions.
- NVIDIA NVML bindings (`pynvml`) to emit structured telemetry; can be wrapped inside BADC to log per
  HawkEars invocation.
- Nsight Systems / Nsight Compute for deep profiling sessions when we tune chunk sizes.
- Optional DCGM exporters if we need Prometheus/Grafana integration on Sockeye (depends on cluster
  policy).

## Proposed workflow
1. Implement a small monitoring helper (`badc gpu monitor`) that spawns `nvidia-smi` sampling at a
   configurable interval and writes JSON/CSV alongside HawkEars outputs.
2. Add CLI flag `--emit-gpu-telemetry` on chunk/infer commands to enable NVML logging during batch
   runs.
3. During chunk-size probing, capture both GPU utilization and CUDA OOM errors to correlate max
   chunk length with VRAM usage.
4. Auto-detect available GPUs via NVML or `nvidia-smi -L`, capture model names + VRAM, and expose
   them to the scheduler. Default worker pool size = number of GPUs (cap at environment limit).
5. For Sockeye runs (up to 4 GPUs), detect `CUDA_VISIBLE_DEVICES` and log per-device stats; when
   only 2 GPUs are present (dev server), adapt scheduling accordingly.
6. Run HawkEars processes in parallel (one per GPU) with affinity controlled via environment
   variables or CLI flags (e.g., `CUDA_VISIBLE_DEVICES=0`).
7. Store telemetry summaries in `notes/chunking.md` and/or a dedicated `data/telemetry/` folder for
   reproducibility.

## Baseline snapshot — 2025-12-09 (dev Quadro RTX 4000)

- Command: ``badc infer monitor --log data/telemetry/infer/XXXX-000_20251001_093000_20251208T215527Z.jsonl --tail 15``
- Dataset: bogus 7-minute clip, chunked into 15 × 30 s windows, single-GPU HawkEars run.
- Observations:
  - GPU 0 (Quadro RTX 4000, 8 GB) reported ~9.6 s runtime per chunk with utilization averaging ~4.5 % (min 0 %, max 14 %) because HawkEars works sequentially on relatively short clips.
  - VRAM usage plateaued at 5743 MiB throughout the run (≈70 % of available memory), aligning with the chunk-size heuristic captured in `notes/chunking.md`.
  - Telemetry sparked lines show stable utilization/memory trends; fans/power remained at idle (~10 W) per `nvidia-smi`.
- Next steps:
  - Repeat the monitor capture on Sockeye (4× GPUs) once the job array harness lands to compare concurrency scaling.
  - Extend telemetry monitor docs with the new snapshot so operators know what steady-state looks like on the dev workstation.

## Open questions
- Does Sockeye allow Nsight profiling, or do we need administrator approval?
- Should GPU monitoring run continuously via a daemon, or only when BADC commands execute?
- How do we surface utilization stats in the final reports (tables vs. dashboards)?
