Infer Commands
==============

The ``badc infer`` namespace schedules HawkEars (or a stub runner) across local GPUs/CPUs, writes
per-chunk JSON detections, and aggregates results for downstream analysis.

.. contents:: On this page
   :local:
   :depth: 1

Overview
--------

* Input is always a chunk manifest CSV produced by ``badc chunk``.
* Outputs default to ``artifacts/infer`` (or ``<dataset>/artifacts/infer`` when the manifest lives
  inside a DataLad dataset).
* Telemetry is logged under ``data/telemetry/infer/log.jsonl`` so long runs can be monitored with
  ``badc telemetry``.
* ``--print-datalad-run`` exposes a ready-to-use command for provenance-friendly workflows.

``badc infer run``
------------------

Run HawkEars against every chunk listed in the manifest.

Usage::

   badc infer run MANIFEST.csv [--max-gpus N] [--cpu-workers N]
       [--output-dir PATH] [--runner-cmd CMD | --use-hawkears]
       [--hawkears-arg ARG ...] [--max-retries N]
       [--print-datalad-run]

Key options:

``--max-gpus``
   Limit how many detected GPUs are used. Defaults to "all GPUs reported by ``nvidia-smi``".
``--cpu-workers``
   Worker count when no GPUs exist (or when a CPU-only run is desired). Minimum 1.
``--runner-cmd``
   Custom executable to run per chunk (e.g., a container wrapper). Mutually exclusive with
   ``--use-hawkears``.
``--use-hawkears``
   Invoke the vendored HawkEars ``analyze.py`` script directly. BADC injects chunk/audio arguments
   and parses ``HawkEars_labels.csv`` into JSON detections.
``--hawkears-arg``
   Repeatable passthrough argument (e.g., ``--hawkears-arg --config`` ``--hawkears-arg config.yaml``).
``--max-retries``
   Number of automatic retries per chunk when the runner exits non-zero (default 2).
``--output-dir``
   Override the destination for JSON outputs. When omitted *and* chunks live in a DataLad dataset,
   BADC writes under ``<dataset>/artifacts/infer`` so the files remain inside the dataset boundary.
``--print-datalad-run``
   Instead of running inference, emit a ``datalad run`` command tailored to the manifest/output pair.

Workflow notes:

* Worker pool: BADC pairs each chunk with a ``GPUWorker`` (index + UUID) derived from ``nvidia-smi``.
  When no GPUs are detected, a CPU thread pool drives the runner.
* Telemetry: every chunk emits a JSON record with timestamps, runtime, status, GPU index, and output
  folder. Monitor progress via ``badc telemetry --log <file>``.
* Failure handling: if any worker raises an exception, the scheduler stops submitting new jobs and
  re-raises the first error after threads finish.

Example::

   badc infer run data/datalad/bogus/manifests/GNWT-290.csv \
       --use-hawkears --max-gpus 2 --hawkears-arg --confidence --hawkears-arg 0.7

``badc infer aggregate``
------------------------

Summarize detection JSON into a CSV that analysts can ingest into notebooks, DuckDB, or dashboards.

Usage::

   badc infer aggregate artifacts/infer --output artifacts/aggregate/summary.csv

Behavior:

* Walks the ``detections_dir`` and parses each JSON file via ``badc.aggregate`` helpers.
* Emits a CSV with one row per detection event (columns include chunk_id, call label, start/end, and
  HawkEars score).
* Skips empty directories with a warning so it is safe to run even before inference completes.

Common pattern::

   badc infer aggregate <dataset>/artifacts/infer --output <dataset>/artifacts/aggregate/summary.csv

Combine with ``datalad run`` or ``git annex`` metadata to track how raw detections feed downstream
reports.
