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
   imported into notebooks or attached to CHANGE_LOG entries for asynchronous reviews.

Step 4 — Notebook/SQL exploration
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
