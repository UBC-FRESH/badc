Usage Overview
==============

The snippets below show the canonical BADC workflow end to end. Each section links back to the
corresponding CLI reference page so you can dive deeper when needed.

.. contents::
   :local:
   :depth: 1

.. _usage-bootstrap:

Bootstrap a checkout
--------------------
The CLI entry point is ``badc``. After cloning the repo, initialise submodules and connect the bogus
DataLad dataset so sample audio is available locally::

   $ git submodule update --init --recursive
   $ badc data connect bogus --pull

``badc data connect`` records the dataset path in ``~/.config/badc/data.toml`` (see
:doc:`cli/data`). You can confirm the registry at any time::

   $ badc data status
   Tracked datasets:
    - bogus: connected (/home/gep/projects/badc/data/datalad/bogus)

To detach the dataset (and optionally drop annexed content)::

   $ badc data disconnect bogus --drop-content
   Dataset bogus marked as disconnected; data removed.

.. _usage-chunk-examples:

Chunk audio and build manifests
-------------------------------
Refer to :doc:`cli/chunk` for option details. A typical sequence:

1. Probe a file to estimate viable chunk durations::

      $ badc chunk probe data/datalad/bogus/audio/XXXX-000_20251001_093000.wav           --initial-duration 120
      Probe placeholder: max chunk 120.00s for ...

2. Generate a manifest without writing audio (hashes optional)::

      $ badc chunk manifest data/datalad/bogus/audio/XXXX-000_20251001_093000.wav           --chunk-duration 60 --hash-chunks           --output manifests/XXXX-000_20251001_093000.csv
      Wrote manifest with chunk duration 60s to manifests/XXXX-000_20251001_093000.csv (with hashes)

3. Split chunks to disk and emit a manifest in one pass::

      $ badc chunk run data/datalad/bogus/audio/XXXX-000_20251001_093000.wav           --chunk-duration 60           --overlap 5           --output-dir artifacts/chunks           --manifest manifests/XXXX-000_20251001_093000.csv
      Chunks written to artifacts/chunks; manifest at manifests/XXXX-000_20251001_093000.csv

When planning large batch jobs, pair ``badc chunk run`` with ``datalad run`` (see
:doc:`howto/chunk-audio`) so provenance is captured alongside the generated WAVs.

.. _usage-infer-examples:

Run inference
-------------
The :doc:`cli/infer` page covers every option; the quick hits below show common patterns.

Stub/local runs (no HawkEars, great for CI)::

   $ badc infer run manifests/XXXX-000_20251001_093000.csv        --runner-cmd "echo hawkears-stub"
   Processed 3 jobs; outputs stored in artifacts/infer

Leverage HawkEars directly (requires CUDA + vendor checkout)::

   $ badc infer run manifests/XXXX-000_20251001_093000.csv        --use-hawkears        --hawkears-arg --confidence        --hawkears-arg 0.7
   Processed 3 jobs; outputs stored in artifacts/infer

CPU-only fallback (e.g., developers without GPUs)::

   $ badc infer run manifests/XXXX-000_20251001_093000.csv --cpu-workers 4
   Processed 3 jobs; outputs stored in artifacts/infer

Preview a ``datalad run`` command without executing jobs::

   $ badc infer run manifests/XXXX-000_20251001_093000.csv --print-datalad-run
   Run the following from the dataset root (/home/gep/projects/badc/data/datalad/bogus):
     datalad run -m "badc infer ..." --input manifests/... --output artifacts/infer -- badc infer run ...

When chunk inputs live inside a DataLad dataset (for example ``data/datalad/bogus``), inference
outputs default to ``<dataset>/artifacts/infer`` so you can immediately ``datalad save`` and push.

GPU planning helpers::

   $ badc gpus
   Detected GPUs:
    - #0: NVIDIA Quadro RTX 4000 (8129 MiB)

Use ``--max-gpus`` to cap the worker pool or ``--cpu-workers`` to bypass GPU detection entirely.

.. _usage-aggregate-telemetry:

Aggregate detections and monitor telemetry
------------------------------------------
Summarise JSON detections into a CSV via :doc:`cli/infer`::

   $ badc infer aggregate artifacts/infer        --output artifacts/aggregate/summary.csv
   Wrote detection summary to artifacts/aggregate/summary.csv

Tail recent telemetry entries (see :doc:`cli/misc`) to monitor long-running jobs::

   $ badc telemetry --log data/telemetry/infer/log.jsonl
   Telemetry records (4):
   [success] GNWT-290_chunk_1 (GPU 0) 2025-12-06T18:22:11 runtime=12.4

Telemetries are JSONL files, so you can also ingest them into notebooks or log shippers for
dashboards.

See also
--------

* :doc:`cli/data` – dataset helpers.
* :doc:`cli/chunk` – chunk probe/split/manifest/run parameters.
* :doc:`cli/infer` – inference, aggregation, and telemetry options.
* :doc:`howto/infer-hpc` – SLURM-ready instructions for Sockeye/Chinook deployments.
