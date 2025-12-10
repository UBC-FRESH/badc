End-to-End CLI Pipeline
=======================

This guide stitches the chunking, inference, aggregation, and reporting CLIs into a single,
reproducible workflow that produces DataLad-tracked artifacts ready for Erin's Phase 2 analytics
review.

Prerequisites
-------------
* ``badc`` installed in an activated virtual environment.
* Target DataLad dataset cloned and connected via ``badc data connect`` (e.g., ``data/datalad/bogus``).
* HawkEars vendor repo fetched via ``git submodule update --init --recursive`` (only needed when
  running with ``--use-hawkears``).
* GPUs visible via ``badc gpus`` (or provide ``--cpu-workers`` for stub runs).

Step 1 — Chunk the dataset
--------------------------
Generate manifests and chunk WAVs for every recording, capturing the plan for downstream commands
and ensuring each chunk directory records ``.chunk_status.json``::

   $ badc chunk orchestrate data/datalad/bogus \
       --pattern "*.wav" \
       --chunk-duration 60 \
       --overlap 0 \
       --plan-json plans/chunks.json \
       --apply \
       --include-existing \
       --workers 4

Notes:

* ``plans/chunks.json`` captures every manifest/chunk directory so inference can reference the exact
  recordings just processed.
* The orchestrator writes ``artifacts/chunks/<recording>/.chunk_status.json`` with
  ``status="completed"`` whenever chunking succeeds. ``badc infer orchestrate`` refuses to run when
  this status is missing or not ``completed``, keeping GPU time aligned with finished chunk jobs.

Step 2 — Run inference (plus aggregation bundle)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Feed the saved chunk plan into the inference orchestrator, reuse completed telemetry summaries when
available, and attach the aggregation/report bundle so Phase 2 artifacts land under
``artifacts/aggregate`` automatically::

   $ badc infer orchestrate data/datalad/bogus \
       --chunk-plan plans/chunks.json \
       --include-existing \
       --resume-completed \
       --apply \
       --bundle \
       --bundle-aggregate-dir artifacts/aggregate \
       --bundle-bucket-minutes 30 \
       --stub-runner \
       --no-record-datalad

Tips:

* Drop ``--stub-runner`` and add ``--use-hawkears`` when you are ready to call the vendor runner.
* For Sockeye submissions, append ``--sockeye-script artifacts/sockeye/badc.sh`` plus the
  ``--sockeye-*`` overrides; the generated script now validates chunk status before chaque array task.

Step 3 — Review + save artifacts
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Each inference run generates:

* ``artifacts/infer/<recording>/`` detection JSON/CSV files.
* ``artifacts/telemetry/infer/<recording>.jsonl`` telemetry logs plus resumable summaries.
* ``artifacts/aggregate/<RUN_ID>*`` quicklook CSVs, Parquet exports, and DuckDB bundles from
  ``--bundle``.

Capture the results in DataLad and sync upstream::

   $ cd data/datalad/bogus
   $ datalad save artifacts -m "End-to-end chunk+infer bundle"
   $ datalad push --to origin

Step 4 — Analyze
~~~~~~~~~~~~~~~~
Open ``docs/notebooks/aggregate_analysis.ipynb`` (or your own notebooks) and point it at the new
``artifacts/aggregate/<RUN_ID>.duckdb`` / Parquet bundle. Python helpers in
``badc.duckdb_helpers`` provide ready-to-use pandas DataFrames for ``label_summary``,
``recording_summary``, and ``timeline_summary`` views.

Next steps
----------
* For HPC runs, rely on ``badc infer orchestrate --sockeye-script`` with ``--sockeye-resume-completed``/
  ``--sockeye-bundle`` plus the chunk-status guard described above.
* When chunking or inference needs to resume partially, re-run the commands with
  ``--include-existing`` / ``--allow-partial-chunks`` while trusting the status files to skip work
  that already completed.
