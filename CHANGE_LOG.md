# 2025-12-10 — Resume-summary CLI wiring
- ``badc infer run`` now accepts ``--resume-summary`` to skip chunks already marked ``success`` in a
  scheduler summary JSON. The CLI loads the summary before scheduling, prints skip/orphaned counts,
  and embeds the flag in ``--print-datalad-run`` output with dataset-relative paths so reruns stay
  provenance-friendly.
- ``badc infer orchestrate --apply`` gained ``--resume-completed``: when enabled it looks for the
  telemetry ``*.summary.json`` per plan, automatically passes ``--resume-summary`` (both for direct
  runs and the generated ``datalad run`` command), and warns when no summary exists. This makes
  dataset-scale retries idempotent without manual flag plumbing.
- Added unit tests covering resume parsing/skip logic, datalad command rendering, and the new
  orchestrate flag; docs/how-tos now document both ``--resume-summary`` and ``--resume-completed``.
- Commands executed (reran after the `_telemetry_summary_path` tweak to keep tooling honest):
  - `source .venv/bin/activate && ruff format src tests`
  - `source .venv/bin/activate && ruff check src tests`
  - `source .venv/bin/activate && pytest`
  - `source .venv/bin/activate && sphinx-build -b html docs _build/html -W`
  - `source .venv/bin/activate && pre-commit run --all-files`

# 2025-12-10 — Resume workflow validation run
- Exercised ``--resume-summary`` on the refreshed bogus manifest
  (``data/datalad/bogus/manifests/XXXX-000_20251001_093000.csv``) and confirmed that the summary at
  ``data/datalad/bogus/artifacts/telemetry/XXXX-000_20251001_093000_20251210T025842Z.jsonl.summary.json``
  skips all 15 chunks with the expected console diagnostics.
- Verified ``badc infer orchestrate --resume-completed``: the first ``--apply`` pass produced
  ``data/datalad/bogus/artifacts/telemetry/infer/XXXX-000_20251001_093000.jsonl`` and the follow-up
  run reused its summary automatically, logging the “resume enabled” warning and skipping every chunk
  without manual CLI flags per manifest.
- Notes updated in ``notes/inference-plan.md`` with the telemetry paths and workflow recap.
- Commands executed:
  - `source .venv/bin/activate && badc infer run data/datalad/bogus/manifests/XXXX-000_20251001_093000.csv --cpu-workers 1`
  - `source .venv/bin/activate && badc infer run data/datalad/bogus/manifests/XXXX-000_20251001_093000.csv --resume-summary data/datalad/bogus/artifacts/telemetry/XXXX-000_20251001_093000_20251210T025842Z.jsonl.summary.json`
  - `source .venv/bin/activate && badc infer orchestrate data/datalad/bogus --manifest-dir manifests --include-existing --apply --stub-runner --no-record-datalad`
  - `source .venv/bin/activate && badc infer orchestrate data/datalad/bogus --manifest-dir manifests --include-existing --apply --stub-runner --no-record-datalad --resume-completed`

# 2025-12-10 — Bogus dataset orchestrate bundle validation
- Re-chunked the refreshed bogus dataset (five GNWT recordings) via
  ``badc chunk orchestrate --include-existing --apply`` to regenerate manifests and chunk WAVs inside
  ``data/datalad/bogus`` (recorded with DataLad so future reruns stay deterministic).
- Normalized each manifest's ``recording_id`` column to match the human-readable stem so inference
  outputs land in ``artifacts/infer/<recording>`` instead of hashed annex names, which unblocks the
  new ``--bundle`` automation.
- Ran ``badc infer orchestrate --apply --bundle`` (stub runner) across every manifest; each recording
  now has fresh inference JSON, telemetry summaries, quicklook CSVs, Parquet reports, and DuckDB
  bundles under ``artifacts/aggregate/GNWT*`` for Phase 2 analytics review.
- Saved the new inference/aggregation artifacts plus telemetry to ``data/datalad/bogus`` and pushed
  the dataset to ``origin``; syncing to ``arbutus-s3`` is still blocked by missing
  ``AWS_ACCESS_KEY_ID``/``AWS_SECRET_ACCESS_KEY`` credentials.
- Commands executed:
  - `source .venv/bin/activate && badc chunk orchestrate data/datalad/bogus --include-existing --apply --no-record-datalad`
  - `python - <<'PY' ...` *(rewrite manifest `recording_id` columns to match the manifest stem; see repo history for the inline script)*
  - `source .venv/bin/activate && badc infer orchestrate data/datalad/bogus --manifest-dir manifests --include-existing --apply --bundle --bundle-bucket-minutes 30 --stub-runner --no-record-datalad`
  - `datalad save artifacts/infer artifacts/aggregate artifacts/telemetry/infer manifests -m "Bogus dataset orchestrate bundle run"`
  - `datalad push --to origin`
  - `datalad push --to arbutus-s3` *(failed: AWS credentials unavailable, so remote sync deferred)*

# 2025-12-10 — Sockeye resume/bundle script docs
- Regenerated a Sockeye SLURM array script for the bogus dataset with both
  ``--sockeye-resume-completed`` and ``--sockeye-bundle`` so each array task automatically skips
  completed chunks and produces quicklook/Parquet/DuckDB bundles after inference.
- Captured the workflow in ``docs/hpc/sockeye.rst`` (new “Automated script generation” section) and
  ``notes/inference-plan.md`` so operators know how to reuse the script located at
  ``artifacts/sockeye/bogus_bundle.sh``.
- Commands executed:
  - `source .venv/bin/activate && badc infer orchestrate data/datalad/bogus --manifest-dir manifests --include-existing --sockeye-script artifacts/sockeye/bogus_bundle.sh --sockeye-job-name badc-bogus --sockeye-account pi-fresh --sockeye-partition gpu --sockeye-gres gpu:4 --sockeye-time 06:00:00 --sockeye-cpus-per-task 8 --sockeye-mem 64G --sockeye-resume-completed --sockeye-bundle --sockeye-bundle-aggregate-dir artifacts/aggregate --sockeye-bundle-bucket-minutes 30 --stub-runner`

# 2025-12-10 — DuckDB notebook refresh
- Updated ``docs/notebooks/aggregate_analysis.ipynb`` to target the refreshed bogus dataset:
  ``RUN_ID`` now defaults to ``GNWT-114_20230509_094500``, the notebook reads per-recording
  Parquet/DuckDB bundles emitted by ``badc report bundle``, and the DuckDB section queries
  ``artifacts/aggregate/<RUN_ID>.duckdb`` instead of the legacy ``detections.duckdb``.
- Added a DuckDB-powered timeline plot sourced from the ``timeline_summary`` view so reviewers can
  visualize bucketed detections directly in the notebook alongside the existing label bar chart.
- Commands executed:
  - `python - <<'PY' ...` *(in-place JSON edit to retarget RUN_ID, DuckDB paths, and append the new timeline plotting cell; see git history for the full snippet)*
  - `source .venv/bin/activate && ruff format src tests`
  - `source .venv/bin/activate && ruff check src tests`
  - `source .venv/bin/activate && pytest`
  - `source .venv/bin/activate && sphinx-build -b html docs _build/html -W`
  - `source .venv/bin/activate && pre-commit run --all-files`

# 2025-12-10 — Aggregation bundle helper
- Added ``badc report bundle`` to run the quicklook, parquet, and DuckDB reporting commands in one
  pass. The helper derives output directories from the Parquet stem (``detections_quicklook/``,
  ``detections_parquet_report/``, ``detections_duckdb_exports/``, ``detections.duckdb``) while
  offering overrides/toggles for each stage.
- README + CLI/how-to docs now describe the bundle workflow, and ``notes/roadmap.md`` reflects the
  Phase 2 aggregation progress.
- Extended ``tests/test_report_cli.py`` with a regression test that exercises the bundle command and
  verifies all artifacts are produced.
- Commands executed:
  - `source .venv/bin/activate && ruff format src tests`
  - `source .venv/bin/activate && ruff check src tests`
  - `source .venv/bin/activate && pytest`
  - `source .venv/bin/activate && sphinx-build -b html docs _build/html -W`
  - `source .venv/bin/activate && pre-commit run --all-files`

# 2025-12-10 — DuckDB helper API
- Added ``badc.duckdb_helpers`` with ``load_duckdb_views`` / ``verify_bundle_schema`` so notebooks/tests
  can load the ``label_summary`` / ``recording_summary`` / ``timeline_summary`` views from bundle
  `.duckdb` files without re-writing SQL. This will anchor the Phase 2 datastore closure task.
- New unit tests (``tests/test_duckdb_helpers.py``) build a temporary DuckDB database, assert the helper
  returns pandas DataFrames, and verify schema validation fails when views are missing.
- ``docs/cli/report.rst`` and ``docs/howto/aggregate-results.rst`` now document the DuckDB schema,
  reference the helper module, and show how to load bundle views in Python. The aggregation notebook
  (`docs/notebooks/aggregate_analysis.ipynb`) imports the helper for its DuckDB sections so reviewers
  see a real-world example. ``notes/roadmap.md`` marks the Phase 2 datastore bullet complete.
- Commands executed:
  - `source .venv/bin/activate && ruff format src tests`
  - `source .venv/bin/activate && ruff check src tests`
  - `source .venv/bin/activate && pytest`

# 2025-12-10 — Scheduler summary + Sockeye log dir
- ``badc infer run`` now records per-chunk retry metadata (`last_backoff_s`, `last_error`) in the
  scheduler summary JSON, emits a `*.workers.csv` alongside every telemetry log, and warns in the
  console whenever chunks retried or failed so operators can triage hotspots immediately.
- ``JobExecutionError`` exposes the same metadata, and `_run_scheduler` propagates it into the summary
  so resume tooling/HPC logs no longer need to scrape the raw telemetry JSONL.
- Added ``--sockeye-log-dir`` to ``badc infer orchestrate --sockeye-script``; generated scripts now
  create the log directory, point both telemetry and resume arrays at `${LOG_DIR}/<recording>.jsonl`,
  log whether the resume summary exists, and print bundle artifact paths after reporting completes.
- `docs/hpc/sockeye.rst`` documents how to stash logs under `$SCRATCH`, and ``notes/roadmap.md`` now
  marks the Phase 2 scheduler bullet complete.
- ``docs/howto/infer-local.rst`` highlights the new `*.workers.csv` output so local runs capture the
  same analytics that HPC operators expect.
- Tests updated (`tests/test_infer_cli.py`, `tests/test_hawkears_runner.py`) to cover the new summary
  fields, worker CSV, and failure metadata.
- Commands executed:
  - `source .venv/bin/activate && ruff format src tests`
  - `source .venv/bin/activate && ruff check src tests`
  - `source .venv/bin/activate && pytest`

# 2025-12-10 — Sockeye resume flag
- ``badc infer orchestrate`` now accepts ``--sockeye-resume-completed``. When generating a Sockeye
  array script the helper emits a ``RESUMES`` array and appends ``--resume-summary`` automatically
  whenever the telemetry ``*.summary.json`` exists, so reruns skip chunks that already finished.
- The Sockeye how-to plus CLI docs describe the new flag, and ``tests/test_infer_cli.py`` verifies
  the emitted script wiring.
- Commands executed:
  - `source .venv/bin/activate && ruff format src tests`
  - `source .venv/bin/activate && ruff check src tests`
  - `source .venv/bin/activate && pytest`
  - `source .venv/bin/activate && sphinx-build -b html docs _build/html -W`
  - `source .venv/bin/activate && pre-commit run --all-files`

# 2025-12-10 — Orchestrate bundle automation
- Added ``--bundle`` (plus ``--bundle-*`` overrides) to ``badc infer orchestrate`` so local
  ``--apply`` runs automatically invoke ``badc infer aggregate`` + ``badc report bundle`` per
  recording. Reports now land under ``artifacts/aggregate/`` without extra commands, keeping quicklook
  CSVs, parquet summaries, and DuckDB databases in sync with inference outputs.
- ``docs/cli/infer.rst`` / ``docs/howto/aggregate-results.rst`` / README updated to describe the
  workflow, and new CLI tests cover the bundle + Sockeye script paths.
- Commands executed:
  - `source .venv/bin/activate && ruff format src tests`
  - `source .venv/bin/activate && ruff check src tests`
  - `source .venv/bin/activate && pytest`
  - `source .venv/bin/activate && sphinx-build -b html docs _build/html -W`
  - `source .venv/bin/activate && pre-commit run --all-files`

# 2025-12-10 — Scheduler resume + Sockeye array helper
- ``badc infer run`` now writes a resumable ``*.summary.json`` next to every telemetry log, recording
  per-worker metrics and the status of each chunk. ``run_job`` logs backoff delays, `_run_scheduler`
  tracks per-chunk outcomes, and tests cover the new summary file so interrupted runs can resume
  cleanly.
- Added ``--sockeye-script`` (plus related ``--sockeye-*`` overrides) to ``badc infer orchestrate``;
  the command now emits a ready-to-submit Sockeye SLURM array script (one manifest per array task),
  eliminating the need to handcraft sbatch templates.
- Updated docs/how-tos/roadmap to describe the summary JSON, live retry sparkline, and Sockeye
  workflow; ``docs/notebooks/aggregate_analysis.ipynb`` now includes a DuckDB bar chart example fed
  directly from the generated `.duckdb` database.
- Commands executed:
  - `.venv/bin/ruff format src tests`
  - `.venv/bin/ruff check src tests`
  - `.venv/bin/pytest`
  - `.venv/bin/sphinx-build -b html docs _build/html -W`
  - `.venv/bin/pre-commit run --all-files`

# 2025-12-10 — DuckDB aggregation helper
- Added ``badc report duckdb`` to materialize canonical detections into a DuckDB database (with
  helper views) and print top labels/recordings/timeline buckets directly in the CLI while emitting
  optional CSV exports. The command leaves behind a `.duckdb` file so Erin can run ad-hoc SQL
  immediately.
- Documented the workflow in ``docs/cli/report.rst``, extended the README + roadmap/pipeline notes,
  and covered it with a CLI regression test.
- Commands executed:
  - `.venv/bin/ruff format src tests`
  - `.venv/bin/ruff check src tests`
  - `.venv/bin/pytest`
  - `.venv/bin/sphinx-build -b html docs _build/html -W`
  - `.venv/bin/pre-commit run --all-files`

# 2025-12-10 — Telemetry monitor retry counters
- Extended ``badc infer monitor`` to display per-GPU retry attempts, failed-attempt totals, a retry
  sparkline, and the attempt counter in the live event tail so long-running jobs expose flaky chunks
  instantly. The CLI helper now parses ``details.attempt`` from telemetry, new helper columns render
  in the Rich table, and the docs/how-to/notes call out the enhanced telemetry view.
- Tests cover the new columns to guard against regressions in the monitor output.
- Commands executed:
  - `.venv/bin/ruff format src tests`
  - `.venv/bin/ruff check src tests`
  - `.venv/bin/pytest`
  - `.venv/bin/sphinx-build -b html docs _build/html -W`
  - `.venv/bin/pre-commit run --all-files`

# 2025-12-09 — Inference scheduler retry metrics
- Extended ``badc.hawkears_runner.run_job`` to return a structured ``JobResult`` (attempts + retry
  counts) and raise ``JobExecutionError`` when retries are exhausted so the scheduler can summarize
  flaky chunks without scraping telemetry logs.
- Updated ``badc infer run``'s worker summary with new columns for retries and failed attempts,
  tracked per worker inside ``_run_scheduler``; docs/how-tos/notes now describe the richer table and
  tests cover the new accounting.
- Commands executed:
  - `.venv/bin/ruff format src tests`
  - `.venv/bin/ruff check src tests`
  - `.venv/bin/pytest`
  - `.venv/bin/sphinx-build -b html docs _build/html -W`
  - `.venv/bin/pre-commit run --all-files`

# 2025-12-09 — Inference scheduler CPU/worker summary uplift
- Switched ``--cpu-workers`` defaults to ``0`` so GPU detection drives concurrency by default while
  still guaranteeing at least one CPU worker when no GPUs are found; added optional CPU slots even
  when GPUs are present and surfaced the new flag throughout ``badc infer run``, ``infer orchestrate``,
  and the TOML config loader.
- Taught ``_run_scheduler`` to track per-worker success/failure counts and return them so
  ``badc infer run`` now prints a Rich summary table (GPU/CPU label, total jobs, failures) at the end
  of every run; CLI docs/how-tos/usage notes now call out the summary behavior and the additive CPU
  worker model.
- Propagated ``--cpu-workers`` through ``badc infer orchestrate`` plans/JSON exports/datalad commands,
  refreshed ``notes/inference-plan.md`` / ``notes/pipeline-plan.md`` / roadmap context, and tightened
  tests for both the scheduler summary and the orchestrator flag plumbing.
- Commands executed:
  - `.venv/bin/ruff format src tests`
  - `.venv/bin/ruff check src tests`
  - `.venv/bin/pytest`
  - `.venv/bin/sphinx-build -b html docs _build/html -W` *(failed: infer-local.rst indentation; fixed before rerun)*
  - `.venv/bin/sphinx-build -b html docs _build/html -W`
  - `.venv/bin/pre-commit run --all-files`

# 2025-12-09 — Chunk orchestrator scaffold
- Added ``src/badc/chunk_orchestrator.py`` plus the ``badc chunk orchestrate`` CLI command to scan a
  dataset's ``audio/`` tree, skip recordings that already have manifests, emit per-recording chunk
  plans, and (with ``--apply``) run ``badc chunk run`` directly.
- Documented the workflow in ``docs/cli/chunk.rst`` and expanded ``docs/howto/chunk-audio.rst`` +
  README to explain how to use the planner for Phase 2 automation. Added
  ``notes/chunk-orchestrator.md`` and updated ``notes/pipeline-plan.md`` / roadmap context.
- Tests cover the planner + CLI (`tests/test_chunk_orchestrator.py`, `tests/test_chunk_cli.py`).

# 2025-12-09 — GPU monitoring roadmap closure
- Marked the Phase 1 GPU monitoring task complete: ``badc infer monitor --follow`` already exposes
  per-GPU utilization + VRAM sparklines, and `notes/gpu-monitoring.md` now documents the baseline
  telemetry captured on the dev Quadro RTX 4000 box (log
  `data/telemetry/infer/XXXX-000_20251001_093000_20251208T215527Z.jsonl`). Sockeye/multi-GPU runs
  will reuse the same tooling in Phase 2.

# 2025-12-09 — GPU telemetry baseline
- Captured a baseline `badc infer monitor` snapshot for the bogus HawkEars run (telemetry log
  `data/telemetry/infer/XXXX-000_20251001_093000_20251208T215527Z.jsonl`) and summarized the dev
  Quadro RTX 4000 utilization/VRAM observations in `notes/gpu-monitoring.md`.
- Provides a reference point before we profile multi-GPU Sockeye jobs.

# 2025-12-09 — HawkEars smoke test
- Added `tests/smoke/test_hawkears_smoke.py`, a gated end-to-end test that runs `badc infer
  run-config` against a single bogus chunk when `BADC_RUN_HAWKEARS_SMOKE=1`; ensures JSON and
  telemetry artifacts are produced without dirtying the DataLad dataset.
- Documented how to trigger the smoke test in `docs/howto/infer-local.rst`.
- Commands executed:
  - `pytest` (smoke test skipped unless the env flag is set)
  - `ruff format src tests`
  - `ruff check src tests`
  - `sphinx-build -b html docs _build/html -W`
  - `pre-commit run --all-files`

# 2025-12-09 — Phase 1 chunk-size validation closure
- Marked the roadmap chunk-size discovery task complete now that `badc chunk probe` + the HawkEars
  validation run (telemetry log `data/telemetry/infer/XXXX-000_20251001_093000_20251208T215527Z.jsonl`)
  confirm the heuristic on the dev GPUs.
- Added a status section to `notes/chunking.md` detailing the validation evidence and capturing a
  follow-up idea for automating future re-validations (`badc chunk validate` stub).
- Commands executed:
  - `apply_patch notes/roadmap.md`
  - `apply_patch notes/chunking.md`

# 2025-12-09 — Config-driven `badc infer run-config`
- Added ``badc infer run-config`` so teams can point at TOML presets (e.g.,
  ``configs/hawkears-local.toml``) instead of retyping long CLI invocations; the command reuses the
  existing scheduler, supports ``--print-datalad-run``, and validates HawkEars extra args.
- Documented the workflow across the CLI reference, usage guide, and local inference how-to; added a
  regression test covering the new command.
- Commands executed:
  - `mkdir -p configs`

# 2025-12-09 — HawkEars config schema + docs
- Added ``configs/hawkears-local.toml`` as the canonical HawkEars runner template covering manifest
  paths, GPU/CPU limits, telemetry, and passthrough HawkEars arguments so local scripts/notebooks
  can launch ``badc infer run`` without repeating flags.
- Expanded ``docs/howto/infer-local.rst`` with a config-driven workflow (TOML example + launcher
  snippet) and cross-linked the schema back to ``notes/pipeline-plan.md``.
- Updated ``notes/pipeline-plan.md`` and ``notes/roadmap.md`` to record the finalized configuration
  surface and mark the Phase 1 task complete.
- Commands executed:
  - `mkdir -p configs`

# 2025-12-09 — DataLad push to origin + arbutus-s3
- Re-sourced `setup/datalad_config.sh` to populate AWS credentials and reran dataset pushes so the
  bogus DataLad dataset mirrors the validation artifacts on both GitHub and the Chinook S3 remote.
- Confirmed `datalad push --to origin` had no further metadata to publish and `datalad push --to
  arbutus-s3` copied all annexed artifacts (chunks, quicklook exports, canonical Parquet/CSV,
  validation outputs) to the object store.
- Commands executed:
  - `source setup/datalad_config.sh`
  - `cd data/datalad/bogus`
  - `datalad push --to origin`
  - `datalad push --to arbutus-s3`

# 2025-12-09 — HawkEars validation + parser fix
- Validated ``badc infer run --use-hawkears`` end-to-end on the bogus manifest with a fresh output
  root (``data/datalad/bogus/artifacts/infer_validation``) so we could bypass existing git-annex
  symlinks, capture telemetry
  (``data/telemetry/infer/XXXX-000_20251001_093000_20251208T215527Z.jsonl``), and confirm GPU 0
  sustains ~9.5 s per 30 s chunk without CUDA errors.
- Fixed `_parse_hawkears_labels` to treat both the chunk filename and the resolved annex object
  name as valid so HawkEars detections (Ruffed Grouse, WTSP, Magnolia Warbler, etc.) finally flow
  into the per-chunk JSON and canonical Parquet export.
- Updated ``notes/chunking.md`` with the validation run details + telemetry path and corrected the
  CLI/docs (usage guide, how-to, HPC recipes, CLI reference) to reference the actual HawkEars flags
  (`--min_score`, `--band 0|1`) so future runs do not fail with ``unrecognized arguments``.
- Aggregated the new JSON outputs into
  ``data/datalad/bogus/artifacts/aggregate/XXXX-000_20251001_093000_validation_summary.csv`` and
  ``..._validation_detections.parquet`` for Phase 2 analytics.
- Commands executed:
  - `.venv/bin/python vendor/HawkEars/analyze.py -h`
  - `.venv/bin/badc infer run data/datalad/bogus/manifests/XXXX-000_20251001_093000.csv --use-hawkears --max-gpus 1`
  - `.venv/bin/badc infer run data/datalad/bogus/manifests/XXXX-000_20251001_093000.csv --use-hawkears --max-gpus 1 --output-dir data/datalad/bogus/artifacts/infer_validation`
  - `rm -rf data/datalad/bogus/artifacts/infer_validation`
  - `.venv/bin/badc infer run data/datalad/bogus/manifests/XXXX-000_20251001_093000.csv --use-hawkears --max-gpus 1 --output-dir data/datalad/bogus/artifacts/infer_validation`
  - `.venv/bin/badc infer aggregate data/datalad/bogus/artifacts/infer_validation --manifest data/datalad/bogus/manifests/XXXX-000_20251001_093000.csv --output data/datalad/bogus/artifacts/aggregate/XXXX-000_20251001_093000_validation_summary.csv --parquet data/datalad/bogus/artifacts/aggregate/XXXX-000_20251001_093000_validation_detections.parquet`
  - `.venv/bin/ruff format src tests`
  - `.venv/bin/ruff check src tests`
  - `.venv/bin/pytest`
  - `.venv/bin/sphinx-build -b html docs _build/html -W`
  - `.venv/bin/pre-commit run --all-files`

# 2025-12-09 — DataLad plan update
- Documented the current bogus dataset workflow (submodule attach instructions, `badc data connect`
  flow, Arbutus S3 sync) and outlined the Chinook production dataset strategy (special remote setup,
  credential handling, and operator bootstrap steps) in `notes/datalad-plan.md`.
- Commands executed:
  - `apply_patch notes/datalad-plan.md`

# 2025-12-09 — Chunk probe telemetry utility
- Replaced the placeholder ``badc chunk probe`` logic with a real WAV-aware estimator: it now reads
  sample rate / channels / bit depth, detects GPUs, performs a binary search to find the largest
  chunk size that fits within ~80 % of a GPU's VRAM, and records every attempt to
  ``artifacts/telemetry/chunk_probe/*.jsonl``.
- Added CLI options for ``--max-duration``, ``--tolerance``, ``--gpu-index``, and ``--log`` so probes
  can be tailored per environment. Rich output now surfaces the recommended duration and the latest
  attempts for quick debugging.
- Updated docs (README, CLI reference, usage guide) and ``notes/chunking.md`` to reflect the new
  behavior; chunk CLI tests now create real WAV fixtures to exercise the flow.
- Commands executed:
  - `ruff format src tests`
  - `ruff check src tests`
  - `pytest`
  - `.venv/bin/pytest`
  - `sphinx-build -b html docs _build/html -W`
  - `.venv/bin/pre-commit run --all-files`

# 2025-12-08 — Quicklook notebook wiring
- Ran ``badc report quicklook --parquet ... --output-dir ...`` on the bogus dataset so label/
  recording/chunk CSV exports exist under ``artifacts/aggregate/XXXX-000_20251001_093000_quicklook``
  (tracked via ``datalad save`` in the submodule).
- Extended ``docs/notebooks/aggregate_analysis.ipynb`` to load the quicklook CSVs, plot detections per
  label, and visualize chunk timelines; updated the notebook index + how-to guide to reference the
  new workflow so Erin can review analytics without touching DuckDB directly.
- Roadmap now records that the quicklook notebook milestone is complete and shifts focus back to the
  chunk-size probe and data-management tasks.
- Commands executed:
  - `.venv/bin/badc report quicklook --parquet data/datalad/bogus/artifacts/aggregate/XXXX-000_20251001_093000_detections.parquet --output-dir data/datalad/bogus/artifacts/aggregate/XXXX-000_20251001_093000_quicklook`
  - `cd data/datalad/bogus && datalad save artifacts/aggregate/XXXX-000_20251001_093000_quicklook -m "Add quicklook exports"`
  - `ruff format src tests`
  - `ruff check src tests`
  - `pytest`
  - `.venv/bin/pytest`
  - `sphinx-build -b html docs _build/html -W`
  - `.venv/bin/pre-commit run --all-files`

# 2025-12-08 — DuckDB quicklook helper
- Added ``badc report quicklook`` plus the underlying ``aggregate.quicklook_metrics`` helper so
  canonical Parquet files can be turned into top-label tables, recording summaries, and per-chunk
  timelines in one command. ASCII sparklines expose detection bursts directly in the terminal, and
  ``--output-dir`` writes CSV snapshots (labels/recordings/chunks) for notebooks.
- Updated README, CLI docs, usage/how-to guides, and the roadmap to highlight the new workflow.
- Tests now cover the helper + CLI, and the documentation note for Phase 2 aggregation reflects the
  deliverable.
- Commands executed:
  - `ruff format src tests`
  - `ruff check src tests`
  - `pytest`
  - `sphinx-build -b html docs _build/html -W`
  - `.venv/bin/pre-commit run --all-files`

# 2025-12-08 — Telemetry monitor rolling trends
- Extended ``badc infer monitor`` with rolling utilization/VRAM trends: new helper utilities build
  ASCII sparklines over the last ~24 telemetry samples per GPU, exposing how busy each device stays
  during ``--follow`` sessions. Summary rows now include utilization history, VRAM history, and
  truncated averages alongside the existing success/failure counters.
- Added unit tests for the sparkline generator + summary aggregator, refreshed the monitor CLI test,
  and documented the new trends in README, CLI reference, and usage guide.
- Commands executed:
  - `ruff format src tests`
  - `ruff check src tests`
  - `pytest`
  - `sphinx-build -b html docs _build/html -W`
  - `.venv/bin/pre-commit run --all-files`

# 2025-12-08 — Telemetry monitor per-GPU stats
- Redesigned ``badc infer monitor`` so the GPU table now shows per-device event counts,
  success/failure tallies, average runtimes, utilization trends (min/avg/max), and peak VRAM usage
  derived from the recorded ``gpu_metrics`` blocks. Added helper utilities to aggregate telemetry
  entries and updated the CLI tests to cover the richer output.
- The monitor tail continues to show recent chunk events but now shares the same metric extractor,
  ensuring utilization/memory snapshots match the summary view across both tables.
- Documentation (README, usage guide, CLI reference) now calls out the per-GPU stats so operators
  know what to expect during long HawkEars runs.
- Commands executed:
  - `ruff format src tests`
  - `ruff check src tests`
  - `pytest`
  - `sphinx-build -b html docs _build/html -W`
  - `.venv/bin/pip install pre-commit`
  - `.venv/bin/pre-commit run --all-files`

# 2025-12-08 — Bogus dataset HawkEars smoke run
- Debugged GPU visibility in the new container: confirmed `badc gpus` after checking `nvidia-smi`
  (plain + `sudo`) so CUDA-backed inference can run on the two Quadro RTX 4000 cards.
- Initialised the data submodules, reconnected the bogus DataLad dataset, and hydrated the annexed
  audio so bogus fixtures are available locally; telemetry now records GPU utilization/memory for
  every chunk in `data/datalad/bogus/artifacts/telemetry/`.
- Ran a full end-to-end pass (`badc infer run --use-hawkears --manifest
  data/datalad/bogus/manifests/XXXX-000_20251001_093000.csv --max-gpus 1`) to generate chunk WAVs,
  HawkEars JSON detections, canonical CSV/Parquet outputs, and aggregate summaries that show real
  species hits (WTSP, BAWW, BTNWs, etc.).
- Validated the Parquet/CSV via `badc report summary
  data/datalad/bogus/artifacts/aggregate/XXXX-000_20251001_093000_detections.parquet`, confirming
  the manifest-aware aggregation schema and telemetry plumbing behave as designed.
- Commands executed:
  - `badc gpus`
  - `nvidia-smi`
  - `sudo nvidia-smi`
  - `git submodule update --init --recursive`
  - `badc data connect bogus --pull`
  - `git annex sync origin`
  - `datalad get -r .`
  - `badc infer run --use-hawkears --manifest data/datalad/bogus/manifests/XXXX-000_20251001_093000.csv --max-gpus 1`
  - `badc report summary data/datalad/bogus/artifacts/aggregate/XXXX-000_20251001_093000_detections.parquet`

# 2025-12-08 — HawkEars detection metadata
- Hooked `badc infer run --use-hawkears` into the real HawkEars output format: `_parse_hawkears_labels`
  now captures label codes/names, detection end offsets, and the HawkEars `model_version` so every
  per-chunk JSON contains the true detections with confidences.
- Extended the canonical detection schema (`badc.aggregate.DetectionRecord`) to include detection
  end times, label metadata, model version, chunk hashes, and dataset roots. CSV/Parquet writers now
  serialize these fields and manifest-aware enrichment fills gaps when custom runners omit metadata.
- Docs (README, CLI reference, usage/how-to) highlight the richer detection payload, and the
  HawkEars helper exposes `get_hawkears_version` for provenance. Tests cover the new schema and CSV
  header as well as the HawkEars parser updates.
- Commands executed:
  - `ruff format src tests`
  - `ruff check src tests`
  - `pytest`
  - `sphinx-build -b html docs _build/html -W`

# 2025-12-08 — Manifest-aware aggregation
- `badc infer aggregate` now accepts `--manifest` so chunk metadata (start/end offsets, hashes,
  recording IDs) can be recovered from the original manifest when custom runners omit it from their
  JSON outputs. The Parquet + CSV exports now point at the real chunk paths and infer dataset roots
  automatically.
- `badc.aggregate.load_detections` enriches detections with manifest data and uses `find_dataset_root`
  to populate provenance; unit tests cover the new behavior alongside CLI coverage for the manifest
  flag.
- Docs (README, CLI reference, usage/how-to) now highlight the manifest option in the aggregation
  workflow so operators know when to supply it.
- Commands executed:
  - `ruff format src tests`
  - `ruff check src tests`
  - `pytest`
  - `sphinx-build -b html docs _build/html -W`

# 2025-12-08 — DuckDB reporting helpers
- Fixed the Parquet summarizer (`badc.aggregate.summarize_parquet`) so it accepts valid group-by
  columns, runs parameterised DuckDB queries, and now powers the new reporting CLI/test coverage.
- Extended `badc infer aggregate` with a `--parquet` flag that writes the canonical detections table
  alongside the CSV summary and reports the generated path in the CLI.
- Added `badc report summary` (plus docs) to load the Parquet file, group by label and/or recording,
  print Rich tables, and optionally emit another CSV; README/usage/how-to pages now walk through the
  workflow end-to-end.
- Documented the DuckDB analytics workflow in `docs/howto/aggregate-results.rst`, refreshed the CLI
  reference (new report page, cross-links), and added regression tests for Parquet exports,
  summariser validation, telemetry monitor output, and the report CLI.
- Commands executed:
  - `ruff format src tests`
  - `ruff check src tests`
  - `pytest`
  - `sphinx-build -b html docs _build/html -W`

# 2025-12-07 — Telemetry monitor + canonical detections
- Added `badc infer monitor` with Rich-based GPU/telemetry tables (supports `--follow` refreshes),
  powered by the per-run telemetry logs introduced earlier.
- Embed chunk metadata and runner information in HawkEars JSON outputs so aggregation can compute
  recording-relative timestamps and checksums.
- `badc infer aggregate` now produces a canonical CSV (chunk offsets, absolute timestamps, runner)
  and supports `--parquet` exports via DuckDB for Phase 2 analytics.
- Module updates:
  - `src/badc/infer_scheduler.py` captures manifest offsets/metadata in `InferenceJob`.
  - `src/badc/hawkears_runner.py` writes chunk metadata, runner labels, and GPU metrics into each
    JSON payload.
  - `src/badc/aggregate.py` provides Parquet helpers and extended detection schema.
- Documentation refreshed to cover the new monitor command, telemetry behavior, and Parquet option.
- Tests added for telemetry monitor CLI, aggregate parsing, Parquet export, and GPU metric parsing.
- Commands executed:
  - `ruff format src tests`
  - `ruff check src tests`
  - `pytest`
  - `sphinx-build -b html docs _build/html -W`

# 2025-12-07 — Inference telemetry + GPU metrics
- `badc infer run` now writes run-specific telemetry logs (defaulting to
  `data/telemetry/infer/<manifest>_<timestamp>.jsonl` or `<dataset>/artifacts/telemetry/…`) and
  surfaces the path in CLI output plus `--print-datalad-run`. A new `--telemetry-log` option allows
  overriding the location.
- Telemetry records now include per-GPU utilization/memory snapshots collected via `nvidia-smi`,
  and `hawkears_runner` forwards these metrics for both success/failure events.
- Added regression tests for telemetry path helpers, GPU metric parsing, and CLI output updates,
  plus documentation/README notes covering the new behavior.
- Commands executed:
  - `ruff format src tests`
  - `ruff check src tests`
  - `pytest`
  - `sphinx-build -b html docs _build/html -W`

# 2025-12-07 — Data disconnect uses datalad drop
- `badc data disconnect --drop-content` now invokes `datalad drop --recursive --reckless auto`
  whenever the dataset has `.datalad` metadata and DataLad is on PATH, ensuring annexed content is
  removed cleanly before deleting the directory.
- Added regression tests covering both the DataLad-aware path and the fallback `shutil.rmtree`
  path, plus documentation updates describing the behavior.
- Commands executed:
  - `ruff format src tests`
  - `ruff check src tests`
  - `pytest`
  - `sphinx-build -b html docs _build/html -W`

# 2025-12-07 — Data CLI status details
- Enriched `badc data status` with `--details` and `--show-siblings`, including filesystem checks,
  detection of DataLad datasets, and sibling listings pulled from `datalad siblings` when available.
- Added registry helpers and tests so git submodules and plain git clones are reported accurately
  alongside DataLad datasets.
- Commands executed:
  - `ruff format src tests`
  - `ruff check src tests`
  - `pytest`
  - `sphinx-build -b html docs _build/html -W`

# 2025-12-07 — Data connect handles git submodules
- Taught `badc data connect` to detect datasets that are already present as git submodules (e.g.,
  `data/datalad/bogus`) so it records them without trying to `datalad update`, which previously
  failed with “Could not determine update target”.
- Recorded these submodule-backed datasets with a `git-submodule` method flag and added regression
  tests covering the new behavior.
- Commands executed:
  - `ruff format src tests`
  - `ruff check src tests`
  - `pytest`
  - `sphinx-build -b html docs _build/html -W`

# 2025-12-07 — GPU detection diagnostics
- Updated `badc gpus`/`badc infer run` to surface `nvidia-smi` failures (e.g. NVML permission errors),
  ensuring operators see why GPU detection fell back to CPUs.
- Documented the troubleshooting workflow in `README.md` and `docs/usage.rst`, plus added a CLI test
  that exercises the new warning path.
- Commands executed:
  - `ruff format src tests`
  - `ruff check src tests`
  - `pytest`
  - `sphinx-build -b html docs _build/html -W`

# 2025-12-07 — Usage walkthroughs
- Rewrote `docs/usage.rst` with anchored CLI walkthroughs (bootstrap, chunking, inference, telemetry) and linked each CLI reference page back to those examples.
- Added roadmap notes capturing the completed worked-example milestone.
- Commands executed:
  - `ruff format src tests`
  - `ruff check src tests`
  - `pytest`
  - `sphinx-build -b html docs _build/html -W`
  - `pre-commit run --all-files`

# 2025-12-07 — CLI help excerpts + HPC doc expansion
- Embedded Typer help excerpts in the chunk/data/infer/misc CLI pages so users can read argument syntax without invoking the commands.
- Expanded the Sockeye/Chinook/Apptainer HPC docs and the Sockeye how-to with GPU planning, job-array patterns, and notebook hand-off guidance to satisfy roadmap item 3.
- Updated `notes/documentation-plan.md` to log the finished option-table/help work and restate the remaining documentation milestones.
- Commands executed:
  - `ruff format src tests`
  - `ruff check src tests`
  - `pytest`
  - `sphinx-build -b html docs _build/html -W`
  - `pre-commit run --all-files`

# 2025-12-07 — CLI option references
- Added list-table option summaries to `docs/cli/chunk.rst`, `docs/cli/data.rst`, `docs/cli/infer.rst`, and `docs/cli/misc.rst` so every command page now satisfies the documentation-plan requirement for option tables.
- Updated `notes/documentation-plan.md` to record the completed option-table pass and capture the next deliverables (help snapshots, HPC guides).
- Commands executed:
  - `ruff format src tests`
  - `ruff check src tests`
  - `pytest`
  - `sphinx-build -b html docs _build/html -W`
  - `pre-commit run --all-files`

# 2025-12-07 — CLI docstrings for API reference
- Upgraded every Typer command/helper in `badc.cli.main` to NumPy-style docstrings so the Sphinx API reference now exposes parameter/return semantics instead of one-line placeholders.
- This satisfies the documentation-plan milestone for seeding the CLI module with rich docstrings before expanding the API reference.
- Commands executed:
  - `ruff format src tests`
  - `ruff check src tests`
  - `pytest`
  - `sphinx-build -b html docs _build/html -W`
  - `pre-commit run --all-files`

# 2025-12-07 — README docs link fix
- Updated the README docs link to the new GitHub Pages URL (https://ubc-fresh.github.io/badc/) and checked off the scratch task.
- Commands executed:
  - `ruff format src tests` (not needed; no code changes)
  - `ruff check src tests` (not needed)
  - `pytest` (not needed)
  - `sphinx-build -b html docs _build/html -W` (not needed)
  - `pre-commit run --all-files` (not needed)

# 2025-12-07 — Rebrand to Compiler
- Renamed all public references from Bird Acoustic Data Cruncher to Bird Acoustic Data Compiler (README, docs, CLI banner, AGENTS, roadmap, API docstrings) so messaging and acronym stay consistent.
- Marked the scratch note complete to reflect the rename decision.
- Commands executed:
  - `ruff format src tests`
  - `ruff check src tests`
  - `pytest`
  - `sphinx-build -b html docs _build/html -W`
  - `pre-commit run --all-files`

# 2025-12-06 — Notebook gallery scaffold
- Documented the planned chunk probe / stub infer / aggregate analysis notebooks (repo layout, execution guidelines) and added starter `.ipynb` files under `docs/notebooks/` so contributors can iterate inside a consistent structure.
- Linked the gallery to the actual notebooks via nbsphinx and removed the placeholder `.rst` wrappers so the pages render on the published docs.
- Commands executed:
  - `ruff format src tests`
  - `ruff check src tests`
  - `pytest`
  - `sphinx-build -b html docs _build/html -W`
  - `pre-commit run --all-files`

# 2025-12-06 — HPC docs baseline
- Filled in `docs/hpc/sockeye.rst`, `docs/hpc/chinook.rst`, and `docs/hpc/apptainer.rst` with the agreed UBC ARC workflows (resource requests, DataLad push/pull patterns, container build instructions).
- Added the `docs/howto/infer-hpc.rst` cookbook so people can submit HawkEars runs on Sockeye without spelunking notes.
- Updated `notes/documentation-plan.md` to reflect the completed HPC documentation slice and capture remaining follow-ups (credential screenshots, notebook gallery).
- Commands executed:
  - `ruff format src tests`
  - `ruff check src tests`
  - `pytest`
  - `sphinx-build -b html docs _build/html -W`
  - `pre-commit run --all-files`

# 2025-12-06 — Chunking docstrings
- Ported `badc.chunking` to the same NumPy-style docstring format (module + public helpers) so the autosummary page finally renders real descriptions.
- Commands executed:
  - `ruff format src tests`
  - `ruff check src tests`
  - `pytest`
  - `sphinx-build -b html docs _build/html -W`
  - `pre-commit run --all-files`

# 2025-12-06 — API docstring sweep kickoff
- Added NumPy-style docstrings plus attribute descriptions for the core modules feeding the Sphinx API docs (`badc.audio`, `badc.aggregate`, `badc.chunk_writer`, `badc.data`, `badc.gpu`, `badc.hawkears`, `badc.hawkears_runner`, `badc.infer_scheduler`, and `badc.telemetry`).
- Updated `notes/documentation-plan.md` to record the modules covered so far and highlight the remaining surfaces (CLI commands, chunking helper stubs, etc.).
- Commands executed:
  - `ruff format src tests`
  - `ruff check src tests`
  - `pytest`
  - `sphinx-build -b html docs _build/html -W`
  - `pre-commit run --all-files`

# 2025-12-06 — Chunk & infer CLI docs
- Replaced the placeholder chunk/infer/misc CLI reference pages with full usage guides that cover
  manifest schema, overlap behavior, concurrency knobs, telemetry, and the `--print-datalad-run`
  helper.
- Updated `notes/documentation-plan.md` to capture the completed CLI milestone and focus the next
  actions on docstrings + HPC guides.
- Commands executed:
  - `ruff format src tests`
  - `ruff check src tests`
  - `pytest`
  - `sphinx-build -b html docs _build/html -W`
  - `pre-commit run --all-files`

# 2025-12-06 — Data CLI + datalad run docs
- Enabled `nbsphinx` plus Napoleon NumPy-only parsing in `docs/conf.py` so we can document notebook
  workflows and enforce the docstring contract from `AGENTS.md`.
- Filled in `docs/cli/data.rst` with end-to-end guidance for `badc data connect/disconnect/status`,
  including config file details, automation tips, and examples.
- Authored the first full how-to (`docs/howto/datalad-run.rst`) showing how to pair `badc infer run`
  with `datalad run` so inference outputs stay inside the dataset that supplied the audio.
- Initial `pytest` invocation failed because the editable install still referenced the pre-rename
  path; rerunning `pip install -e .` re-pointed the package and the test suite now passes.
- Commands executed:
  - `python - <<'PY' ...` (insert `nbsphinx` into docs/conf.py)
  - `python - <<'PY' ...` (append Napoleon/nbsphinx settings)
  - `cat <<'EOF' > docs/cli/data.rst`
  - `cat <<'EOF' > docs/howto/datalad-run.rst`
  - `python - <<'PY' ...` (fix CLI heading underlines)
  - `pip install -e .`
  - `ruff format src tests`
  - `ruff check src tests`
  - `pytest`
  - `sphinx-build -b html docs _build/html -W`
  - `pre-commit run --all-files`

# 2025-12-06 — Documentation scaffolding kickoff
- Enabled `sphinx.ext.autosummary` (with generation) in `docs/conf.py` and expanded
  `notes/documentation-plan.md` with the docstring sweep requirement so every module/function/class
  gets NumPy-style docstrings before autodoc exposure.
- Commands executed:
  - `python - <<'PY' ...` (update docs/conf.py)
  - `python - <<'PY' ...` (update documentation plan note)

# 2025-12-06 — Docs publish via GitHub Pages
- CI workflow now uploads `docs/_build/html` as a Pages artifact on `main` pushes and deploys it
  via `actions/deploy-pages`, so Sphinx docs stay in sync at
  https://ubc-fresh.github.io/bird-acoustic-data-cruncher/. README now links to the published docs.
- Commands executed:
  - `apply_patch .github/workflows/ci.yml README.md`

# 2025-12-06 — Sample audio now lives in DataLad
- Removed the raw WAVs from `data/audio/`, added a README pointing users to
  `data/datalad/bogus/audio/`, refreshed docs/notes/tests to reference the submodule paths, and
  made the bogus bootstrap script look for audio in either `data/audio` or the submodule. This keeps
  large binaries out of the main Git repo.
- Commands executed:
  - `rm data/audio/*.wav`
  - `apply_patch data/audio/README.md AGENTS.md data/chunk_manifest_sample.csv`
  - `apply_patch docs/usage.rst notes/bogus-datalad.md notes/chunking.md notes/datalad-plan.md`
  - `apply_patch notes/erin-notes.md scripts/setup_bogus_datalad.sh tests/test_infer_cli.py`
  - `ruff format src tests`
  - `ruff check src tests`
  - `pytest`
  - `sphinx-build -b html docs _build/html -W`
  - `pre-commit run --all-files`

# 2025-12-06 — HawkEars runner integration
- Added `--use-hawkears` flag to `badc infer run`, implemented the HawkEars subprocess call
  (per-chunk `vendor/HawkEars/analyze.py` invocation) with telemetry logging, parsing of
  `HawkEars_labels.csv` into the JSON payload consumed by `badc infer aggregate`, and added a
  thread-per-worker scheduler so each GPU (or `--cpu-workers` fallback) processes jobs concurrently.
  Outputs now default to `<dataset>/artifacts/infer` when the chunk lives inside a DataLad dataset,
  and `--print-datalad-run` emits a ready-to-use `datalad run ... badc infer run ...` command so
  transforms can be captured with provenance. Stub mode remains the default for CI/tests. Added unit
  tests for the CSV parser plus CLI coverage for the new scheduler + dataset-aware behavior, and
  documented how to pass through HawkEars args.
- Commands executed:
  - `apply_patch src/badc/hawkears_runner.py src/badc/cli/main.py README.md docs/usage.rst`
  - `apply_patch notes/inference-plan.md notes/roadmap.md`
  - `apply_patch tests/test_hawkears_runner.py tests/test_cli.py`
  - `ruff format src tests`
  - `ruff check src tests`
  - `pytest`
  - `sphinx-build -b html docs _build/html -W`
  - `pre-commit run --all-files`

# 2025-12-06 — Bogus dataset submodule
- Pushed the generated dataset in `tmp/badc-bogus-data` to GitHub (`datalad push --to origin`)
  and added `data/datalad/bogus` as a git submodule pointing at `UBC-FRESH/badc-bogus-data`.
  Updated notes/roadmap to mark the wiring complete.
- Commands executed:
  - `source setup/datalad_config.sh && cd tmp/badc-bogus-data && datalad create-sibling-github --existing=reconfigure`
  - `source setup/datalad_config.sh && cd tmp/badc-bogus-data && datalad push --to origin`
  - `git submodule add https://github.com/UBC-FRESH/badc-bogus-data.git data/datalad/bogus`
  - `apply_patch notes/datalad-plan.md notes/bogus-datalad.md notes/roadmap.md`
  - `apply_patch README.md docs/usage.rst`

# 2025-12-06 — Bogus submodule pending
- Tried to add `UBC-FRESH/badc-bogus-data` as `data/datalad/bogus`, but the GitHub repo currently
  has no commits so git refuses to create the submodule. Restored the placeholder README with
  instructions and documented the blocker in `notes/datalad-plan.md`, `notes/bogus-datalad.md`, and
  the roadmap.
- Commands executed:
  - `git rm data/datalad/bogus/README.md` (rolled back after failure)
  - `apply_patch data/datalad/bogus/README.md notes/datalad-plan.md notes/bogus-datalad.md notes/roadmap.md`
  - `ruff format src tests`
  - `ruff check src tests`
  - `pytest`
  - `sphinx-build -b html docs _build/html -W`
  - `pre-commit run --all-files`

# 2025-12-06 — Data CLI connect/disconnect workflow
- Added `src/badc/data.py` plus Typer wiring so `badc data connect/disconnect/status` now clone
  datasets (preferring `datalad` with `git` fallback), record metadata in
  `~/.config/badc/data.toml`, and optionally remove content. Updated README, docs, roadmap, and
  bogus DataLad notes; added CLI regression tests.
- Commands executed:
  - `apply_patch src/badc/data.py src/badc/cli/main.py README.md docs/usage.rst notes/roadmap.md`
  - `apply_patch notes/bogus-datalad.md notes/datalad-plan.md`
  - `apply_patch tests/test_cli.py`
  - `ruff format src tests`
  - `ruff check src tests`
  - `pytest`
  - `sphinx-build -b html docs _build/html -W`
  - `pre-commit run --all-files`

# 2025-12-06 — Bogus dataset caveat
- Updated `notes/datalad-plan.md` with the current limitation: if the bootstrap script fails after
  creating the Arbutus bucket, the reuse logic still can’t recover, so manual bucket/UUID deletion
  is required before rerunning.
- Commands executed:
  - `apply_patch notes/datalad-plan.md`

# 2025-12-06 — Bogus dataset bootstrap status
- Documented in `notes/datalad-plan.md` that the bogus dataset bootstrap succeeded (new Arbutus
  bucket + `UBC-FRESH/badc-bogus-data` GitHub repo) so we can focus on wiring `badc data connect`.
- Commands executed:
  - `apply_patch notes/datalad-plan.md`
  - `ruff format src tests`
  - `ruff check src tests`
  - `pytest`
  - `sphinx-build -b html docs _build/html -W`
  - `pre-commit run --all-files`

# 2025-12-06 — Bogus DataLad bucket guardrails
- Hardened `scripts/setup_bogus_datalad.sh` to detect existing Arbutus buckets, reuse known
  `git-annex-uuid` values, and optionally reset unreadable/conflicting buckets via
  `S3_RESET_CONFLICTING_BUCKET`. Added `S3_EXISTING_REMOTE_UUID` hint + documented knobs in
  `setup/datalad_config.template.sh` and `notes/datalad-plan.md`. Ignored `tmp/` so local datasets
  don’t show up as untracked files.
- Fixed the special-remote reuse call so we now pass `sameas=<uuid>` (per git-annex docs) instead of
  the invalid `--sameas` flag.
- Commands executed:
  - `ruff format src tests`
  - `ruff check src tests`
  - `pytest`
  - `sphinx-build -b html docs _build/html -W`
  - `pre-commit run --all-files`

# 2025-12-06 — Bogus DataLad scaffolding
- Updated `data/datalad/bogus/README.md`, README/docs, and notest to document the upcoming `badc data connect` wiring to `UBC-FRESH/badc-bogus-audio`.
- Commands executed:
  - `echo ... > data/datalad/bogus/README.md`
  - `apply_patch README.md docs/usage.rst`

# 2025-12-06 — Datalad bootstrap script
- Added `setup/datalad_config.template.sh` and `scripts/setup_bogus_datalad.sh` to automate dataset
  creation (`datalad create`, audio copy, GitHub remote, and `git annex initremote` to spawn the S3
  bucket). Documentation updated in `notes/datalad-plan.md`.
- 2025-12-06: Script now shells out to `datalad create-sibling-github` so the GitHub repo is
  auto-created (per lab docs) and uses `GITHUB_ORG`/`GITHUB_REPO_NAME` env vars.
- 2025-12-06: Added S3 bucket reuse detection (reads `git-annex-uuid` and passes `--sameas=UUID` to
  `git annex initremote`) so reruns don’t fail if the bucket already exists.

# 2025-12-06 — HawkEars runner + telemetry hooks
- Added `hawkears_runner.py`, wired `badc infer run --manifest` to process chunk jobs (with retries,
  telemetry, and output dir handling), and documented README/docs/tests updates.
- Commands executed:
  - `ruff format src tests`
  - `ruff check src tests`
  - `pytest`
  - `sphinx-build -b html docs docs/_build/html -W`

# 2025-12-06 — Telemetry record timestamp fix
- Simplified telemetry records to log a single timestamp + runtime (no deprecated UTC warning) and
  updated scheduler logging accordingly.
- Commands executed:
  - `ruff format src tests`
  - `ruff check src tests`
  - `pytest`

# 2025-12-06 — Bogus DataLad workflow note
- Updated `notes/bogus-datalad.md` + roadmap to capture the upcoming `badc data connect` wiring for
  the bogus dataset (clone, connect, disconnect flow).
- Commands executed:
  - `apply_patch notes/bogus-datalad.md`
  - `apply_patch notes/roadmap.md`

# 2025-12-06 — Bogus dataset skeleton
- Created `data/datalad/bogus/README.md` (placeholder) to reserve the submodule mount point for the
  forthcoming bogus DataLad repository.
- Commands executed: `mkdir -p data/datalad/bogus && touch data/datalad/bogus/README.md`

# 2025-12-06 — Data connect/disconnect stubs
- Added CLI stubs for `badc data connect/disconnect` (points to `data/datalad/<name>`), plus README/docs notes ahead of wiring the bogus DataLad repo.
- Commands executed:
  - `ruff format src tests`
  - `ruff check src tests`
  - `pytest`

# 2025-12-06 — HawkEars runner subprocess wiring
- `badc infer run` now shells out to the HawkEars CLI (when `--runner-cmd` is provided), sets
  `CUDA_VISIBLE_DEVICES`, captures stdout/stderr, and logs telemetry per attempt; stub mode remains
  for local testing.
- Commands executed:
  - `ruff format src tests`
  - `ruff check src tests`
  - `pytest`

# 2025-12-06 — HawkEars CLI integration plan
- Noted in `notes/inference-plan.md` that the runner passes GPU index info to the HawkEars CLI
  along with input/config args.
- Commands executed: `apply_patch notes/inference-plan.md`

# 2025-12-06 — HawkEars inference plan
- Added `notes/inference-plan.md` detailing the manifest loader, GPU scheduler, telemetry, and CLI
  requirements for `badc infer run`; roadmap updated accordingly.
- Commands executed:
  - `cat > notes/inference-plan.md`
  - `apply_patch notes/roadmap.md`

# 2025-12-06 — Telemetry utilities
# 2025-12-06 — HawkEars runner plan
- Added retry/backoff details to `notes/inference-plan.md` (up to 2 retries per chunk, telemetry\n+  annotation).\n+- Commands executed: `apply_patch notes/inference-plan.md`\n+\n # 2025-12-06 — Telemetry utilities
- Added `telemetry.py` and hooked it into `infer_scheduler` to log JSONL events per chunk/worker.
- Commands executed:
  - `ruff format src tests`
  - `ruff check src tests`
  - `pytest`
  - `sphinx-build -b html docs docs/_build/html -W`

# 2025-12-06 — Inference telemetry plan
- Expanded `notes/inference-plan.md` with telemetry logging details (JSONL storage, command
  metadata, retry info).
- Commands executed: `apply_patch notes/inference-plan.md`

# 2025-12-06 — Inference scheduler scaffolding
- Added `src/badc/infer_scheduler.py` + CLI hooks so `badc infer run --manifest ...` loads chunk jobs
  and reports detected GPU workers; updated tests to reflect manifest-based invocation.
- Commands executed:
  - `ruff format src tests`
  - `ruff check src tests`
  - `pytest`
  - `sphinx-build -b html docs docs/_build/html -W`

# 2025-12-06 — Chunk manifest path integration
- `badc chunk run` now passes real chunk metadata to the manifest writer so path/hash entries
  reference generated files; tests updated.
- Commands executed:
  - `ruff format src tests`
  - `ruff check src tests`
  - `pytest`
  - `sphinx-build -b html docs docs/_build/html -W`

# 2025-12-06 — Chunk run CLI test
- Added regression test for `badc chunk run` ensuring chunk files + manifest are created.
- Commands executed:
  - `ruff format src tests`
  - `ruff check src tests`
  - `pytest`
  - `sphinx-build -b html docs docs/_build/html -W`

# 2025-12-06 — Chunk run CLI scaffold
- Added `badc chunk run` command (dry-run + chunk writing), chunk writer overlap handling, and docs.
- Commands executed:
  - `ruff format src tests`
  - `ruff check src tests`
  - `pytest`
  - `sphinx-build -b html docs docs/_build/html -W`

# 2025-12-06 — Chunk writer scaffolding
- Introduced `chunk_writer.py` plus updated `badc chunk manifest --hash-chunks` to generate chunk
  files with hashes (still stubbed for real overlap handling and temp layout).
- Commands executed:
  - `ruff format src tests`
  - `ruff check src tests`
  - `pytest`
  - `sphinx-build -b html docs docs/_build/html -W`

# 2025-12-06 — Chunk file plan
- Added `notes/chunk-files.md` outlining the implementation strategy for `badc chunk run`
  (chunk writer + manifest integration) and updated the roadmap accordingly.
- Commands executed:
  - `cat > notes/chunk-files.md`
  - `apply_patch notes/roadmap.md`

# 2025-12-06 — Manifest hashing improvement
- `badc chunk manifest --hash-chunks` now hashes the source file per chunk row (still placeholder
  until actual chunk files exist).
- Commands executed:
  - `ruff format src tests`
  - `ruff check src tests`
  - `pytest`
  - `sphinx-build -b html docs docs/_build/html -W`

# 2025-12-06 — GPU CLI knobs planned
- Noted in `notes/pipeline-plan.md` that `badc infer run` should expose `--max-gpus` and worker
  pool overrides, defaulting to auto-detected GPU counts.
- Commands executed: `apply_patch notes/pipeline-plan.md`

# 2025-12-06 — GPU detection CLI
- Added `badc gpus` command and `src/badc/gpu.py` helper to enumerate GPUs via `nvidia-smi` so we
  can size the HawkEars worker pool per environment.
- Commands executed:
  - `ruff format src tests`
  - `ruff check src tests`
  - `pytest`
  - `sphinx-build -b html docs docs/_build/html -W`

# 2025-12-06 — GPU parallelism planning
- Updated `notes/gpu-monitoring.md` and `notes/pipeline-plan.md` to capture automatic GPU
  detection and multi-process HawkEars scheduling (one worker per GPU with NVML telemetry).
- Commands executed:
  - `apply_patch notes/gpu-monitoring.md`
  - `apply_patch notes/pipeline-plan.md`

# 2025-12-06 — Chunk manifest hashing option
- Added SHA256 utility + `--hash-chunks` option so `badc chunk manifest` can embed real hashes (per
  file for now) and documented the behavior in README/docs + tests.
- Commands executed:
  - `ruff format src tests`
  - `ruff check src tests`
  - `pytest`
  - `sphinx-build -b html docs docs/_build/html -W`

# 2025-12-06 — Manifest hashing note
- Clarified in `notes/chunking.md` that SHA256 hashes must cover the chunk file bytes (not just
  placeholders) when the chunking engine lands.
- Commands executed: `apply_patch notes/chunking.md`

# 2025-12-06 — Chunk manifest follow-ups noted
- Documented in `notes/chunking.md` that `badc chunk manifest` currently writes placeholder hashes
  and needs SHA256 + overlap metadata in the upcoming implementation.
- Commands executed: `apply_patch notes/chunking.md`

# 2025-12-06 — Chunk manifest CLI scaffold
- Added `badc chunk manifest` command, WAV duration helper, sample tests/assets, and documentation
  so manifests can be generated ahead of the full HawkEars wiring.
- Commands executed:
  - `ruff format src tests`
  - `ruff check src tests`
  - `pytest`
  - `sphinx-build -b html docs docs/_build/html -W`

# 2025-12-06 — Chunk manifest sample
- Added a sample chunk manifest CSV (`data/chunk_manifest_sample.csv`) and noted the future
  `badc chunk manifest` command in `notes/chunking.md` to clarify the metadata contract.
- Commands executed:
  - `cat > data/chunk_manifest_sample.csv`
  - `apply_patch notes/chunking.md`

# 2025-12-06 — Aggregation/reporting plan details
- Enriched `notes/pipeline-plan.md` with DuckDB table sketches, QC/report artifact expectations,
  and CLI implications for `badc aggregate/report`.
- Commands executed: `apply_patch notes/pipeline-plan.md`

# 2025-12-06 — Pipeline schema details
- Expanded `notes/pipeline-plan.md` with manifest and detection schema definitions (chunk IDs,
  timestamps, model metadata) so downstream automation has concrete targets.
- Commands executed: `apply_patch notes/pipeline-plan.md`

# 2025-12-06 — Pipeline planning note
- Added `notes/pipeline-plan.md` describing the chunk → infer → aggregate → report stages,
  including manifests, telemetry expectations, and CLI hooks.
- Updated the roadmap to reference the plan in the CLI orchestration task.
- Commands executed:
  - `cat > notes/pipeline-plan.md`
  - `apply_patch notes/roadmap.md`

# 2025-12-06 — Inference CLI scaffolding
- Added `badc infer run|aggregate` placeholder commands plus utility helpers so the full
  chunk→infer→aggregate pipeline shape is represented in the CLI/tests/docs.
- Commands executed:
  - `ruff format src tests`
  - `ruff check src tests`
  - `pytest`
  - `sphinx-build -b html docs docs/_build/html -W`

# 2025-12-06 — Bogus DataLad planning note
- Added `notes/bogus-datalad.md` outlining the lightweight audio dataset we will expose as a test
  submodule for the `badc data connect` workflow.
- Roadmap now references the new note under Phase 3.
- Commands executed:
  - `cat > notes/bogus-datalad.md`
  - `apply_patch notes/roadmap.md`

# 2025-12-06 — Chunk CLI scaffolding
- Added `badc.chunk` subcommands (`probe`, `split`) plus `badc/chunking.py` utilities and tests to
  prepare for the real HawkEars/GPU integration.
- Documented the commands in README/docs and kept CI green via ruff/pytest/Sphinx builds.
- Commands executed:
  - `ruff format src tests`
  - `ruff check src tests`
  - `pytest`
  - `sphinx-build -b html docs docs/_build/html -W`

# 2025-12-06 — Chunking note audio details
- Updated `notes/chunking.md` to document the 60 min (`GNWT-290_20230331_235938.wav`) and 7 min
  (`XXXX-000_20251001_093000.wav`) test clips, highlight the HawkEars reference paper in
  `reference/`, and capture the plan to move these samples into a mini DataLad dataset.
- Commands executed:
  - `apply_patch notes/chunking.md`

# 2025-12-06 — Chunking probe planning note
- Added `notes/chunking.md` detailing the chunk-size probing workflow (binary search, telemetry
  capture, CLI surface) and documenting the GPU inventories we must account for.
- Roadmap now references the note for the chunk-size discovery task.
- Commands executed:
  - `cat > notes/chunking.md`
  - `apply_patch notes/roadmap.md`

# 2025-12-06 — HawkEars submodule onboarding
- Added the HawkEars fork as a git submodule under `vendor/HawkEars` and exposed
  `badc.hawkears.get_hawkears_root()` so CLI/tools can locate it.
- Updated README instructions to remind contributors to run `git submodule update --init --recursive`
  and marked the roadmap task complete.
- Commands executed:
  - `git submodule add https://github.com/UBC-FRESH/HawkEars vendor/HawkEars`
  - `ruff format src tests`
  - `ruff check src tests`
  - `pytest`

# 2025-12-06 — GPU monitoring plan note
- Added `notes/gpu-monitoring.md` outlining tooling (nvidia-smi, NVML, Nsight) and documenting the
  2-GPU dev vs. 4-GPU Sockeye environments so we can verify HawkEars utilizes available CUDA
  capacity.
- Updated `notes/roadmap.md` Detailed Next Steps with a dedicated GPU telemetry task.
- Commands executed:
  - `cat > notes/gpu-monitoring.md`
  - `apply_patch notes/roadmap.md`

# 2025-12-06 — Pre-commit + CI automation
- Added `.pre-commit-config.yaml` with Ruff hooks and documented the setup in `README.md` so local
  workflows stay aligned with the agent contract.
- Introduced `.github/workflows/ci.yml` to run Ruff format/lint, `pytest`, and the Sphinx build on
  every push/PR; marked the roadmap task complete.
- Commands executed:
  - `ruff format src tests`
  - `ruff check src tests`
  - `pytest`
  - `sphinx-build -b html docs docs/_build/html -W`

# 2025-12-06 — DataLad installation guidance
- Expanded `notes/datalad-plan.md` with git-annex + DataLad install instructions (pip extras,
  NeuroDebian/Homebrew, and the `datalad-installer` shortcut) so future setup scripts have a
  canonical reference.
- Commands executed:
  - `apply_patch notes/datalad-plan.md`

# 2025-12-06 — Python/CLI/docs scaffolding
- Added initial project scaffold: `pyproject.toml`, `src/badc` package with Typer CLI stubs,
  editable install via Hatch, and README instructions.
- Introduced tooling + docs baselines: ruff/pytest config, `.gitignore`, `tests/test_cli.py`, and a
  minimal Sphinx tree (`docs/conf.py`, `docs/index.rst`, `docs/usage.rst`) that builds with the
  Furo theme.
- Ran the standard command cadence to prove the scaffold works locally.
- Commands executed:
  - `python -m pip install -e .[dev]`
  - `ruff format src tests`
  - `ruff check src tests`
  - `pytest`
  - `sphinx-build -b html docs docs/_build/html -W`

# 2025-12-06 — DataLad planning note + roadmap update
- Added `notes/datalad-plan.md` describing the bogus/test vs. production DataLad repositories and
  the required `badc data connect|disconnect|status` CLI surface.
- Extended `notes/roadmap.md` with tasks for the new DataLad workflow (Phase 0/2/3) and refreshed
  the "Detailed Next Steps" data-management item.
- Commands executed:
  - `cat > notes/datalad-plan.md`
  - `apply_patch notes/roadmap.md`

# 2025-12-06 — Governance scaffold + roadmap draft
- Added `AGENTS.md` and `CONTRIBUTING.md`, adapted from the FHOPS templates, to codify the coding-agent contract, doc/test expectations, and GPU/HPC data-handling rules for the new project.
- Created `CHANGE_LOG.md` (this file) and `notes/roadmap.md` so future work items, status, and command cadences stay traceable from the outset.
- Commands executed:
  - `cat > AGENTS.md`
  - `cat > CONTRIBUTING.md`
  - `cat > CHANGE_LOG.md`
  - `cat > notes/roadmap.md`
# 2025-12-06 — Detection aggregation CLI
- Implemented `badc infer aggregate` to scan detection JSON outputs, added `aggregate.py`, README/docs updates, and regression tests.
- Commands executed:
  - `ruff format src tests`
  - `ruff check src tests`
  - `pytest`

# 2025-12-06 — Telemetry finish timestamps
- Telemetry records now capture a single timestamp plus `finished_at`, and the HawkEars runner populates success/failure entries (with stdout/stderr snippets).
- Commands executed:
  - `ruff format src tests`
  - `ruff check src tests`
  - `pytest`
# 2025-12-06 — Telemetry monitor command
- Added `badc telemetry --log ...` to read the JSONL log and show the latest entries; documented in README/docs.
- Commands executed:
  - `ruff format src tests`
  - `ruff check src tests`
  - `pytest`
# 2025-12-06 — Roadmap next steps
- Added roadmap bullets for HawkEars JSON parsing + DuckDB work and the upcoming bogus DataLad connect wiring.
- Commands executed: `apply_patch notes/roadmap.md`
- # 2025-12-06 — Detection schema parsing
- Aggregator now reads HawkEars JSON detections (`aggregate.py`) and emits canonical CSV rows
  (recording/chunk/timestamp/label/confidence); tests updated.
- Commands executed:
  - `ruff format src tests`
  - `ruff check src tests`
  - `pytest`
# 2025-12-09 — Chunk probe telemetry logs
- Captured heuristic chunk-probe runs for the bogus 7 min + 60 min recordings using the new CLI and
  recorded the recommended chunk sizes plus telemetry log paths in `notes/chunking.md`.
- Commands executed:
  - `.venv/bin/badc chunk probe data/datalad/bogus/audio/XXXX-000_20251001_093000.wav --initial-duration 60 --max-duration 600 --tolerance 5`
  - `.venv/bin/badc chunk probe data/datalad/bogus/audio/GNWT-290_20230331_235938.wav --initial-duration 120 --max-duration 3600 --tolerance 10`
- Enhanced ``badc chunk orchestrate`` with plan persistence (`--plan-csv/--plan-json`) and an
  ``--apply`` flag that runs ``badc chunk run`` for every recording, so dataset-wide chunking can
  both be previewed and executed in one pass. README/CLI/how-to docs now mention the saved plan
  workflow, and tests cover the new behavior.
# 2025-12-09 — Inference orchestrator
- Added ``src/badc/infer_orchestrator.py`` plus ``badc infer orchestrate`` so we can scan manifests
  (or saved chunk plans), print inference plans, save CSV/JSON summaries, emit ready-to-run
  ``datalad run`` commands, and even execute the entire run list via ``--apply``. README, CLI docs,
  and the infer how-to now document the workflow; tests cover the planner + CLI path.

# 2025-12-09 — Phase 2 parquet report helper
- Added ``badc report parquet`` plus ``badc.aggregate.parquet_report``/``ParquetReport`` so Erin can
  turn canonical detections into CSV/JSON artifacts (labels, recordings, timeline buckets, summary)
  without leaving the CLI.
- Documented the new helper across README, ``docs/cli/report.rst``, and
  ``docs/howto/aggregate-results.rst``; autosummary stubs now list the added APIs, and the pipeline
  plan notes the Phase 2 reporting workflow.
- Introduced ``tests/test_report_cli.py`` (skips if DuckDB is missing) to exercise the new command’s
  export path and caught missing DuckDB gracefully in the CLI.
- Commands executed:
  - ``ruff format src tests``
  - ``ruff check src tests``
  - ``pytest``
  - ``sphinx-build -b html docs _build/html -W``
  - ``pre-commit run --all-files``

# 2025-12-09 — Parquet bundle notebook wiring
- Updated ``docs/notebooks/aggregate_analysis.ipynb`` to load the new ``badc report parquet``
  outputs (labels/recordings/timeline CSVs + ``summary.json``) so plots and tables now reflect the
  CLI-generated artifacts that Erin reviews in Phase 2.
- Added top-recording and bucketed timeline sections plus refreshed markdown narrative explaining
  how to point the notebook at ``<run>_parquet_report`` directories.
- Reintroduced the quicklook example section so the notebook can also visualize the lighter
  ``badc report quicklook`` CSVs (labels + per-chunk timeline) when that workflow is preferred.
- Commands executed:
  - ``ruff format src tests``
  - ``ruff check src tests``
  - ``pytest``
  - ``sphinx-build -b html docs _build/html -W``
  - ``pre-commit run --all-files``

# 2025-12-09 — Chunk run dataset-aware defaults
- ``badc chunk run`` now auto-detects DataLad roots (``.datalad``) and, when present, defaults to
  ``<dataset>/artifacts/chunks/<recording>`` for chunk WAVs and ``<dataset>/manifests/<recording>.csv``
  for manifests; outside datasets, both directories are created next to the audio file.
- Dry-run mode produces realistic metadata (one row per chunk with accurate start/end offsets) so
  planners/datalad commands can preview outputs without writing files.
- ``badc chunk orchestrate --apply`` now wraps executions in ``datalad run`` by default (with a
  ``--no-record-datalad`` escape hatch) so dataset-scale chunking can be triggered from a single
  command while capturing provenance.
- ``badc infer orchestrate --apply`` mirrors the chunk behavior: it executes each manifest in the
  plan immediately and, when `.datalad` plus the CLI are available, automatically wraps the runs in
  `datalad run` (toggle via `--no-record-datalad`). CLI docs/how-tos now describe the workflow, and
  tests cover both the direct and datalad-backed paths.
- Added regression coverage for the new defaults, refreshed the chunk CLI/how-to docs, and updated
  the roadmap + chunk-file implementation note to reflect the Phase 2 progress.
- Commands executed:
  - ``ruff format src tests``
  - ``ruff check src tests``
  - ``pytest``
  - ``sphinx-build -b html docs _build/html -W``
  - ``pre-commit run --all-files``
