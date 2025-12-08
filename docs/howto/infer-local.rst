Run Local HawkEars Inference
============================

This guide walks through running ``badc infer run --use-hawkears`` on the dev workstation (Quadro RTX
4000 GPUs). It supplements the CLI reference with a configuration schema, environment prep, and
end-to-end command snippets so you can test the entire chunk → infer → aggregate cycle locally.

.. contents:: Steps
   :local:
   :depth: 1

Prerequisites
-------------
* `git clone https://github.com/UBC-FRESH/badc.git && cd badc`
* `python -m venv .venv && source .venv/bin/activate`
* `pip install -e .[dev]`
* `git submodule update --init --recursive`
* `badc data connect bogus --pull`
* `datalad get -r data/datalad/bogus` (optional; downloads audio/chunks up-front)
* Confirm GPU visibility: `badc gpus`

HawkEars configuration schema
-----------------------------
All runtime knobs live behind ``badc infer run`` (Typer) options. For repeatability we recommend
capturing them in a simple ``toml``/``yaml`` file (example below) even though the CLI currently
expects flags.

``badc infer run`` key options:

====================  ==================  ========================================================
Flag                  Default             Purpose
====================  ==================  ========================================================
``--use-hawkears``    ``False``           Switch from stub runner to the embedded
                                          ``vendor/HawkEars/analyze.py`` script.
``--max-gpus``        auto-detect         Cap number of GPUs used (one worker per GPU).
``--cpu-workers``     ``1``               Worker count when no GPUs are available.
``--hawkears-arg``    ``[]``              Extra args forwarded verbatim to `analyze.py`
                                          (repeat for each flag, e.g. ``--hawkears-arg --confidence``).
``--runner-cmd``      ``None``            Custom command executed per chunk. Mutually exclusive with
                                          ``--use-hawkears``.
``--output-dir``      ``artifacts/infer`` Output root for JSON/CSV; relocates automatically when the
                                          manifest lives inside a DataLad dataset.
``--telemetry-log``   auto-generated      JSONL log path; defaults to
                                          ``data/telemetry/infer/<manifest>_<timestamp>.jsonl`` or
                                          ``<dataset>/artifacts/telemetry/…`` when the manifest
                                          resides in a DataLad dataset.
``--max-retries``     ``2``               Per-chunk retry budget.
``--print-datalad-run`` ``False``         Print a ready-to-use ``datalad run`` command (no jobs run).
====================  ==================  ========================================================

Sample configuration (``configs/hawkears-local.toml``):

.. code-block:: toml

   [hawkears]
   use_hawkears = true
   manifest = "data/datalad/bogus/manifests/XXXX-000_20251001_093000.csv"
   max_gpus = 1
   hawkears_args = ["--confidence", "0.75", "--batch-size", "4"]
   output_dir = "data/datalad/bogus/artifacts/infer"
   telemetry_log = "data/datalad/bogus/artifacts/telemetry/XXXX-000_20251001_093000_local.jsonl"

Invoke via ``badc infer run`` by interpolating the config values manually or via a small helper
script (future work: Typer subcommand that reads the file directly).

Step 1 — Chunk selection
------------------------
Either reuse existing manifests (e.g., ``data/datalad/bogus/manifests/XXXX-000_20251001_093000.csv``)
or generate new ones:

.. code-block:: console

   $ badc chunk probe data/datalad/bogus/audio/XXXX-000_20251001_093000.wav \
       --initial-duration 60 --max-duration 600 --tolerance 5
   $ badc chunk manifest data/datalad/bogus/audio/XXXX-000_20251001_093000.wav \
       --chunk-duration 60 --hash-chunks \
       --output data/datalad/bogus/manifests/XXXX-000_20251001_093000.csv

Step 2 — Run HawkEars locally
-----------------------------

.. code-block:: console

   $ badc infer run data/datalad/bogus/manifests/XXXX-000_20251001_093000.csv \
       --use-hawkears \
       --max-gpus 1 \
       --hawkears-arg --confidence \
       --hawkears-arg 0.75

Expected outputs:
* JSON detections under ``data/datalad/bogus/artifacts/infer/<recording>/``
* Telemetry log inside ``data/datalad/bogus/artifacts/telemetry/…``
* Console summary listing telemetry path + job counts

Step 3 — Monitor telemetry
--------------------------

.. code-block:: console

   $ badc infer monitor --log data/datalad/bogus/artifacts/telemetry/XXXX-000_20251001_093000_local.jsonl --follow

The monitor shows per-GPU event counts, utilization stats, and rolling VRAM trends. For quick
inspection, use ``badc telemetry --log …`` to just print the latest entries.

Step 4 — Aggregate results
--------------------------

.. code-block:: console

   $ badc infer aggregate data/datalad/bogus/artifacts/infer \
       --manifest data/datalad/bogus/manifests/XXXX-000_20251001_093000.csv \
       --output data/datalad/bogus/artifacts/aggregate/XXXX-000_20251001_093000_summary.csv \
       --parquet data/datalad/bogus/artifacts/aggregate/XXXX-000_20251001_093000_detections.parquet

Follow up with

.. code-block:: console

   $ badc report quicklook --parquet data/datalad/bogus/artifacts/aggregate/XXXX-000_20251001_093000_detections.parquet \
       --output-dir data/datalad/bogus/artifacts/aggregate/XXXX-000_20251001_093000_quicklook
   $ open docs/notebooks/aggregate_analysis.ipynb  # optional pandas plots

Step 5 — Save via DataLad
-------------------------

.. code-block:: console

   $ cd data/datalad/bogus
   $ datalad save -m "Local HawkEars run on XXXX-000_20251001_093000"
   $ datalad push --to origin
   $ datalad push --to arbutus-s3 --data auto

Configuration tips
------------------
* Keep manifests + outputs inside the same DataLad dataset so telemetry and JSON/CSV artifacts are
  annexed together.
* Set `CUDA_VISIBLE_DEVICES` when testing multi-GPU scenarios.
* Use `.venv/bin/badc infer run …` so telemetry references the correct interpreter in virtualenv
  setups.
