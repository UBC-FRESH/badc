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

.. list-table::
   :header-rows: 1

   * - Flag
     - Default
     - Purpose
   * - ``--use-hawkears``
     - ``False``
     - Switch from the stub runner to ``vendor/HawkEars/analyze.py``.
   * - ``--max-gpus``
     - auto-detect
     - Cap number of GPUs used (one worker per GPU).
   * - ``--cpu-workers``
     - ``1``
     - Worker count when no GPUs are available.
   * - ``--hawkears-arg``
     - ``[]``
     - Extra args forwarded verbatim to ``analyze.py`` (repeat per flag, e.g. ``--hawkears-arg --min_score``).
   * - ``--runner-cmd``
     - ``None``
     - Custom command executed per chunk (mutually exclusive with ``--use-hawkears``).
   * - ``--output-dir``
     - ``artifacts/infer``
     - Output root for JSON/CSV; relocates automatically when the manifest lives inside a DataLad dataset.
   * - ``--telemetry-log``
     - auto-generated
     - JSONL log path; defaults to ``data/telemetry/infer/<manifest>_<timestamp>.jsonl`` or ``<dataset>/artifacts/telemetry/…`` inside DataLad datasets.
   * - ``--max-retries``
     - ``2``
     - Per-chunk retry budget.
   * - ``--print-datalad-run``
     - ``False``
     - Print a ready-to-use ``datalad run`` command (no jobs run).

Sample configuration (``configs/hawkears-local.toml``):

.. code-block:: toml

   [runner]
   manifest = "data/datalad/bogus/manifests/XXXX-000_20251001_093000.csv"
   use_hawkears = true
   max_gpus = 1
   cpu_workers = 1
   output_dir = "data/datalad/bogus/artifacts/infer"
   telemetry_log = "data/datalad/bogus/artifacts/telemetry/XXXX-000_20251001_093000_local.jsonl"

   [hawkears]
   extra_args = ["--min_score", "0.75", "--band", "1"]

   [paths]
   dataset_root = "data/datalad/bogus"

Invoke via ``badc infer run`` by interpolating the config values manually or call the helper
command:

.. code-block:: console

   $ badc infer run-config configs/hawkears-local.toml

Each key mirrors the surface documented in ``notes/pipeline-plan.md`` so ops notes and user docs
stay aligned. If you need further customization (e.g., injecting environment-specific defaults),
use a short Python helper:

Config-file driven runs
-----------------------
``configs/hawkears-local.toml`` ships with the repo so you can reuse the same schema across
environments. A tiny launcher script (or notebook cell) can read the file, translate it to CLI
flags, and execute ``badc infer run`` when you need to patch values on the fly:

.. code-block:: console

   $ python - <<'PY'
   import tomllib, shlex, subprocess
   from pathlib import Path

   config = tomllib.loads(Path("configs/hawkears-local.toml").read_text())
   runner = config["runner"]
   hawkears_cfg = config.get("hawkears", {})

   cmd = [
       "badc",
       "infer",
       "run",
       runner["manifest"],
       "--output-dir",
       runner["output_dir"],
       "--max-gpus",
       str(runner["max_gpus"]),
       "--cpu-workers",
       str(runner.get("cpu_workers", 1)),
   ]
   if runner.get("use_hawkears", False):
       cmd.append("--use-hawkears")
   for arg in hawkears_cfg.get("extra_args", []):
       cmd.extend(["--hawkears-arg", arg])
   if telemetry := runner.get("telemetry_log"):
       cmd.extend(["--telemetry-log", telemetry])

   print("Running:", " ".join(shlex.quote(part) for part in cmd))
   subprocess.run(cmd, check=True)
   PY

Tips:

* Keep dataset-relative paths (`data/datalad/...`) so ``datalad run`` captures provenance.
* `extra_args` map 1:1 to HawkEars' ``analyze.py`` arguments (e.g., ``--min_score``).
* Store per-host overrides (GPU count, telemetry path) in separate TOML files, then pass the right
  file to the snippet above.

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
       --hawkears-arg --min_score \
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

Smoke tests
-----------
When you need extra assurance that HawkEars still runs end-to-end, enable the gated smoke test:

.. code-block:: console

   $ BADC_RUN_HAWKEARS_SMOKE=1 pytest tests/smoke/test_hawkears_smoke.py

The test trims the bogus manifest to a single chunk, runs ``badc infer run-config`` (real HawkEars),
and checks that JSON/telemetry artifacts appear under a temporary path. By default the test is
skipped so regular CI does not require GPUs or HawkEars assets.
