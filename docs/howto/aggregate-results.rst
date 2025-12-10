Aggregate Detection Results
===========================

This how-to demonstrates the post-inference workflow: convert HawkEars JSON payloads into the
canonical detection schema, persist a Parquet file, and summarize detections with DuckDB plus the
``badc report`` helpers.

Prerequisites
-------------

* ``badc infer run`` completed and wrote JSON files under ``<dataset>/artifacts/infer``.
* The optional DuckDB dependency is installed (``pip install duckdb``) so ``--parquet`` exports and
  report commands succeed.
* ``badc`` is available on ``PATH`` (editable install or packaged release).

Step 1 — Aggregate JSON to CSV/Parquet
--------------------------------------

1. Point ``badc infer aggregate`` at the inference output directory. Capture both CSV (easy diff) and
   Parquet (columnar analytics) targets::

      badc infer aggregate data/datalad/bogus/artifacts/infer \
          --manifest data/datalad/bogus/manifests/GNWT-290.csv \
          --output data/datalad/bogus/artifacts/aggregate/summary.csv \
          --parquet data/datalad/bogus/artifacts/aggregate/detections.parquet

2. The command crawls all JSON files, injects chunk metadata (start/end offsets, hashes, dataset
   root). When the manifest path is supplied, any missing chunk metadata is retrieved directly from
   the CSV so custom runners do not need to embed it into their JSON payloads. Each detection row
   now carries both relative/absolute start **and** end timestamps, HawkEars label codes/names,
   confidence, runner label, and the HawkEars ``model_version`` extracted from the submodule. The
   command writes the canonical schema described in :mod:`badc.aggregate`.
3. Commit outputs with ``datalad save`` or ``git add`` as appropriate so the provenance of each
   inference batch is preserved.

Step 2 — Summaries via ``badc report summary``
----------------------------------------------

1. Use the Parquet export directly from the CLI::

      badc report summary \
          --parquet data/datalad/bogus/artifacts/aggregate/detections.parquet \
          --group-by label,recording_id \
          --output data/datalad/bogus/artifacts/aggregate/summary_by_label.csv

2. The command runs a DuckDB query (``COUNT(*)`` plus ``AVG(confidence)``) and renders a Rich table.
   Adjust ``--group-by`` to focus on labels, recordings, or the combination thereof.
3. The optional ``--output`` path mirrors the on-screen table so collaborators without DuckDB can
   review the same summary.

Step 3 — Quicklook dashboards via ``badc report quicklook``
-----------------------------------------------------------

1. Run the quicklook command to capture label/recording highlights plus a per-chunk timeline::

      badc report quicklook \
          --parquet data/datalad/bogus/artifacts/aggregate/detections.parquet \
          --top-labels 12 \
          --top-recordings 5 \
          --output-dir data/datalad/bogus/artifacts/aggregate/quicklook

2. The CLI prints Rich tables and ASCII sparklines so you can scan activity bursts directly in the
   terminal. When ``--output-dir`` is set, CSV snapshots land alongside the detections and can be
   imported into notebooks or attached to CHANGE_LOG entries for asynchronous reviews. The
   :doc:`/notebooks/aggregate_analysis` example shows how to load the CSVs with pandas to build plots.

Step 4 — Detailed parquet report
--------------------------------

1. Generate CSV/JSON artifacts for Erin using the new DuckDB-backed helper::

      badc report parquet \
          --parquet data/datalad/bogus/artifacts/aggregate/detections.parquet \
          --bucket-minutes 30 \
          --output-dir data/datalad/bogus/artifacts/aggregate/parquet_report

2. The CLI prints overall stats, richer label/recording tables, and a bucketed timeline (detections
   per N-minute window). The ``--output-dir`` captures ``labels.csv``, ``recordings.csv``,
   ``timeline.csv``, and ``summary.json`` so Erin can drop them straight into her thesis figures or
   notebooks without running DuckDB herself.

Step 4b — Run the bundle helper (optional)
------------------------------------------

When you want the quicklook CSVs, parquet bundle, and DuckDB database in one pass, use::

   badc report bundle \
       --parquet data/datalad/bogus/artifacts/aggregate/detections.parquet \
       --output-dir data/datalad/bogus/artifacts/aggregate \
       --bucket-minutes 30

The command derives ``detections_quicklook/``, ``detections_parquet_report/``,
``detections_duckdb_exports/``, and ``detections.duckdb`` automatically. Toggle individual stages
with ``--no-quicklook`` / ``--no-parquet-report`` / ``--no-duckdb-report`` or override specific
paths (e.g., ``--duckdb-database``) when needed. This is the fastest way to package Phase 2 review
artifacts for Erin after each inference run.

Tip: when running ``badc infer orchestrate --apply`` you can pass ``--bundle`` (plus the optional
``--bundle-*`` overrides) so these aggregation/report steps run automatically after every recording —
no need to invoke the commands manually unless you want custom tweaks.

Step 4c — Roll up a directory of detections
-------------------------------------------

When the aggregate directory holds multiple per-recording Parquet files (e.g., after running
``badc infer orchestrate --apply --bundle`` across a dataset), use the new helper to get a quick
cross-run summary::

   badc report aggregate-dir data/datalad/bogus/artifacts/aggregate \
       --limit 20 \
       --export-dir data/datalad/bogus/artifacts/aggregate/summary_exports

The command scans for ``*_detections.parquet`` (falls back to ``*.parquet`` when bundle outputs use
plain run-prefix names), loads the matches via DuckDB, prints consolidated label/recording
leaderboards, and optionally writes ``label_summary.csv`` / ``recording_summary.csv`` under the
export directory. This is the fastest sanity check to confirm the refreshed bogus dataset (now five
GNWT recordings) still contains the expected vocalizations vs. background noise mix.

Tip: pass ``--bundle-rollup`` to ``badc infer orchestrate`` (enabled automatically in
``badc pipeline run``) to run this helper as soon as the queue drains. By default the rollup exports
land in ``artifacts/aggregate/aggregate_summary/``, so Erin always has a dataset-wide CSV ready
alongside the per-recording bundles.

Step 5 — Materialize a DuckDB database
--------------------------------------

1. Turn the Parquet export into a DuckDB database (views + CSV snapshots) for Erin::

      badc report duckdb \
          --parquet data/datalad/bogus/artifacts/aggregate/detections.parquet \
          --database data/datalad/bogus/artifacts/aggregate/detections.duckdb \
          --bucket-minutes 30 \
          --export-dir data/datalad/bogus/artifacts/aggregate/duckdb_exports

   This creates the ``detections`` table plus three convenience views
   (``label_summary``, ``recording_summary``, ``timeline_summary``), prints the same Rich tables shown
   in ``badc report parquet``, and writes ``label_summary.csv`` / ``recording_summary.csv`` /
   ``timeline.csv`` when ``--export-dir`` is provided.
2. Open the database interactively::

      duckdb data/datalad/bogus/artifacts/aggregate/detections.duckdb
      -- Loading resources from /home/.../.duckdbrc
      D  SELECT * FROM label_summary LIMIT 5;

   Or issue one-off queries::

      duckdb -c "SELECT recording_id, SUM(detections) AS calls \
                 FROM recording_summary ORDER BY calls DESC LIMIT 5" \
          data/datalad/bogus/artifacts/aggregate/detections.duckdb

   The same database can be mounted in notebooks via `duckdb.connect(".../detections.duckdb")` for
   richer charts without re-importing the Parquet file. Prefer the helper
   :func:`badc.duckdb_helpers.load_duckdb_views` when you want ready-made pandas DataFrames for the
   ``label_summary`` / ``recording_summary`` / ``timeline_summary`` views::

      from badc.duckdb_helpers import load_duckdb_views

      views = load_duckdb_views("data/datalad/bogus/artifacts/aggregate/detections.duckdb",
                                limit_labels=10)
      views.label_summary.head()

Step 6 — Notebook/SQL exploration
---------------------------------

1. Open the Parquet file with DuckDB for ad-hoc SQL::

      duckdb -c "SELECT label, COUNT(*) FROM 'data/.../detections.parquet' GROUP BY 1"

2. Or load it from Python::

      import duckdb
      con = duckdb.connect()
      con.execute(
          """
          SELECT recording_id, label, COUNT(*) AS detections
          FROM read_parquet('data/.../detections.parquet')
          GROUP BY 1, 2
          ORDER BY detections DESC
          """
      ).df()

3. Incorporate telemetry (``badc infer monitor`` / ``badc telemetry``) to correlate GPU usage with
   detection density; telemetry logs live alongside the aggregate files when the manifest resides
   within a DataLad dataset.

See also
--------

* :doc:`/cli/infer` for detailed aggregation options and telemetry monitoring.
* :doc:`/cli/report` for additional reporting helpers that will grow alongside Phase 2 analytics.
