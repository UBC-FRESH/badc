Report Commands
===============

Utilities that operate on the canonical detections table (DuckDB/Parquet) live under
``badc report``. They complement :doc:`/cli/infer` by transforming the Parquet export into analyst-
friendly tables or plots.

.. contents:: On this page
   :local:
   :depth: 1

``badc report summary``
-----------------------

Aggregate detections stored in Parquet via DuckDB. The command prints a Rich table (optionally
written to CSV) so analysts can quickly inspect label, recording, or label+recording totals.

Usage::

   badc report summary --parquet artifacts/aggregate/detections.parquet \
       --group-by label,recording_id --output artifacts/aggregate/summary_by_label.csv

Key options
^^^^^^^^^^^

``--parquet``
   Path to the Parquet detections file produced by ``badc infer aggregate --parquet ...``.
``--group-by``
   Comma-separated grouping columns (``label`` or ``recording_id``; defaults to ``label``).
``--output``
   Optional CSV destination mirroring the console output.
``--limit``
   Cap the number of displayed rows (default 20) when the grouping returns many combinations.

Option reference
^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1

   * - Option / Argument
     - Description
     - Default
   * - ``--parquet PATH``
     - Parquet file containing canonical detections.
     - Required
   * - ``--group-by TEXT``
     - Columns (``label``, ``recording_id``) used for aggregation.
     - ``label``
   * - ``--output PATH``
     - Optional CSV path for the rendered summary.
     - Disabled
   * - ``--limit INT``
     - Maximum rows printed to the console.
     - ``20``

Help excerpt
^^^^^^^^^^^^

.. code-block:: console

   $ badc report summary --help
   Usage: badc report summary [OPTIONS]
     Summarize detections via DuckDB (group counts + avg confidence).
   Options:
     --parquet PATH      Parquet detections file.  [required]
     --group-by TEXT     Comma-separated columns to group by (label, recording_id).
     --output PATH       Optional CSV path for the summary.
     --limit INTEGER     Rows to display in console.
     --help              Show this message and exit.

See also
--------

* :doc:`/cli/infer` for emitting the Parquet detections export.
* :doc:`/howto/aggregate-results` for a guided walkthrough that chains ``badc infer aggregate``,
  ``badc report summary``, ``badc report quicklook``, and notebook-ready DuckDB queries.

``badc report quicklook``
-------------------------

Produce a multi-table “quicklook” report that highlights the busiest labels, the loudest recordings,
and a per-chunk detection timeline. The command always targets the canonical Parquet export produced
by ``badc infer aggregate --parquet`` and renders ASCII sparklines directly in the terminal.

Usage::

   badc report quicklook \
       --parquet data/datalad/bogus/artifacts/aggregate/detections.parquet \
       --top-labels 12 \
       --top-recordings 5 \
       --output-dir data/datalad/bogus/artifacts/aggregate/quicklook

Key options
^^^^^^^^^^^

``--parquet``
   Canonical detections Parquet file (required).
``--top-labels``
   Number of label rows to display (default 10).
``--top-recordings``
   Number of recording rows to display (default 5).
``--output-dir``
   Optional directory for CSV exports (``labels.csv``, ``recordings.csv``, ``chunks.csv``).

Option reference
^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1

   * - Option / Argument
     - Description
     - Default
   * - ``--parquet PATH``
     - Path to the canonical detections Parquet file.
     - Required
   * - ``--top-labels INT``
     - Number of label rows to display/export.
     - ``10``
   * - ``--top-recordings INT``
     - Number of recording rows to display/export.
     - ``5``
   * - ``--output-dir PATH``
     - Directory where CSV snapshots will be stored.
     - Disabled

Help excerpt
^^^^^^^^^^^^

.. code-block:: console

   $ badc report quicklook --help
   Usage: badc report quicklook [OPTIONS]
     Generate quicklook tables/plots for canonical detections.
   Options:
     --parquet PATH       Parquet detections file.  [required]
     --top-labels INTEGER
                           Number of label rows to display.
     --top-recordings INTEGER
                           Number of recording rows to display.
     --output-dir PATH    Optional directory for CSV exports.
     --help               Show this message and exit.

Output
^^^^^^

The command prints three Rich tables (labels, recordings, chunk timeline) and an ASCII sparkline
representing detections-per-chunk so you can eyeball bursts of activity without launching a
notebook. When ``--output-dir`` is set the same data lands in CSVs for downstream DuckDB/Pandas
pipelines.

``badc report parquet``
-----------------------

Run richer DuckDB summaries (labels, recordings, timeline buckets) against the canonical Parquet
export. This command is tailored for Phase 2 analytics workflows that need CSV artifacts or JSON
summaries without opening a notebook.

Usage::

   badc report parquet \
       --parquet data/datalad/bogus/artifacts/aggregate/detections.parquet \
       --top-labels 25 \
       --top-recordings 10 \
       --bucket-minutes 30 \
       --output-dir data/datalad/bogus/artifacts/aggregate/parquet_report

Key options
^^^^^^^^^^^

``--parquet``
   Canonical detections Parquet file produced by ``badc infer aggregate --parquet``.
``--top-labels`` / ``--top-recordings``
   How many rows to display/export for each table (defaults: 20 labels, 10 recordings).
``--bucket-minutes``
   Timeline bucket size in minutes; detections are grouped by this window and printed in chronological
   order.
``--output-dir``
   When provided, ``labels.csv``, ``recordings.csv``, ``timeline.csv``, and ``summary.json`` are
   written alongside the console output.

The command prints three Rich tables (labels, recordings, timeline) plus a summary panel with total
detections, label/recording counts, and first/last chunk timestamps. Combine this with
``badc infer orchestrate`` to generate ready-to-review analytics packages for Erin.

``badc report duckdb``
----------------------

Materialize the canonical detections Parquet export into a DuckDB database, create helper views
(``detections``, ``label_summary``, ``recording_summary``, ``timeline_summary``), and print the same
tables Erin reviews in notebooks. This command is ideal when you want a `.duckdb` file for ad-hoc
SQL queries plus CSV exports for downstream workflows.

Usage::

   badc report duckdb \
       --parquet data/datalad/bogus/artifacts/aggregate/detections.parquet \
       --database data/datalad/bogus/artifacts/aggregate/detections.duckdb \
       --bucket-minutes 30 \
       --export-dir data/datalad/bogus/artifacts/aggregate/duckdb_exports

Key options
^^^^^^^^^^^

``--parquet``
   Canonical detections Parquet file produced by ``badc infer aggregate --parquet``.
``--database``
   DuckDB database that will be created (or overwritten) with the detections table and helper views.
``--bucket-minutes``
   Timeline bucket size (minutes) for the aggregated sparkline/table.
``--top-labels`` / ``--top-recordings``
   How many rows to display in the console (defaults: 15 labels, 10 recordings).
``--export-dir``
   Optional directory for CSV exports (``label_summary.csv``, ``recording_summary.csv``, ``timeline.csv``).

Behavior
^^^^^^^^

* Loads the Parquet detections into a DuckDB table called ``detections`` and registers three views for
  common analytics.
* Prints the database summary (detection count, label count, recording count, first/last chunk), top
  labels, top recordings, and a timeline table plus sparkline.
* When ``--export-dir`` is provided, writes CSV snapshots mirroring the console output.
* Leaves behind the DuckDB database so analysts can run ``duckdb artifacts/aggregate/detections.duckdb``
  and continue exploring with SQL or notebooks.
* Reuse the Python helper ``badc.duckdb_helpers.load_duckdb_views`` when you want pandas DataFrames
  for the three views without re-writing SQL in every notebook/test.

DuckDB schema reference
^^^^^^^^^^^^^^^^^^^^^^^

+--------------------+------------------------------+-----------------------------------------------+
| Object             | Columns                      | Notes                                         |
+====================+==============================+===============================================+
| ``detections``     | All fields from              | Canonical detection rows (see                 |
|                    | :class:`badc.aggregate.      | :class:`badc.aggregate.DetectionRecord`).     |
|                    | DetectionRecord`. ``chunk_   | ``chunk_start_ms`` carries the absolute       |
|                    | start_ms`` carries the       | chunk offset (ms) so downstream SQL can build |
|                    | absolute chunk offset (ms).  | absolute timelines.                           |
+--------------------+------------------------------+-----------------------------------------------+
| ``label_summary``  | ``label``, ``label_name``,   | Used for bar charts/leaderboards.             |
|                    | ``detections``,              | ``avg_confidence`` is computed directly       |
|                    | ``avg_confidence``           | inside DuckDB.                                |
+--------------------+------------------------------+-----------------------------------------------+
| ``recording_       | ``recording_id``,            | Columns mirror the CLI tables and the CSV     |
| summary``          | ``detections``,              | exports.                                      |
|                    | ``avg_confidence``           |                                               |
+--------------------+------------------------------+-----------------------------------------------+
| ``timeline_        | ``bucket_index``,            | Bucket duration is controlled via             |
| summary``          | ``bucket_start_ms``,         | ``--bucket-minutes``. Ready for timeline      |
|                    | ``detections``,              | plots (see the updated notebook).             |
|                    | ``avg_confidence``           |                                               |
+--------------------+------------------------------+-----------------------------------------------+

The helper module mentioned above exposes a ``verify_bundle_schema`` function that ensures the
database contains these tables/views and raises a descriptive error when they are missing. This is
useful in CI or notebooks that expect bundle outputs generated by ``badc report bundle``.

``badc report bundle``
----------------------

Create the full Phase 2 artifact set (quicklook CSVs, parquet report bundle, DuckDB database +
exports) with a single command. This is ideal after every inference run so Erin can review the same
tables/plots without re-running CLI commands one-by-one.

Usage::

   badc report bundle \
       --parquet data/datalad/bogus/artifacts/aggregate/detections.parquet \
       --output-dir data/datalad/bogus/artifacts/aggregate \
       --bucket-minutes 30

Behavior:

* Derives paths from the Parquet stem (e.g., ``detections_quicklook``) unless ``--output-dir`` or the
  per-artifact overrides are supplied.
* Invokes ``badc report quicklook`` (unless ``--no-quicklook``), ``badc report parquet`` (unless
  ``--no-parquet-report``), and ``badc report duckdb`` (unless ``--no-duckdb-report``) with the
  provided sizing arguments.
* Writes CSVs to ``<stem>_quicklook`` and ``<stem>_parquet_report``, materializes
  ``<stem>.duckdb``, and mirrors DuckDB summaries into ``<stem>_duckdb_exports``.

Key options:

``--parquet``
   Canonical detections file to summarize (required).
``--output-dir`` / ``--run-prefix``
   Base directory and prefix for derived folders/files. Defaults to ``parquet.parent`` and
   ``parquet.stem``.
``--quicklook/--no-quicklook`` etc.
   Toggle individual stages.
``--parquet-top-labels``, ``--quicklook-top-labels``, ``--duckdb-top-labels`` …
   Control how many rows each report prints/exports.
``--bucket-minutes``
   Shared bucket size for the parquet + DuckDB timeline views.

Example directory layout::

   artifacts/aggregate/
   ├── detections.parquet
   ├── detections_quicklook/
   │   ├── labels.csv
   │   ├── recordings.csv
   │   └── chunks.csv
   ├── detections_parquet_report/
   │   ├── labels.csv
   │   ├── recordings.csv
   │   ├── timeline.csv
   │   └── summary.json
   ├── detections.duckdb
   └── detections_duckdb_exports/
       ├── label_summary.csv
       ├── recording_summary.csv
       └── timeline.csv

``badc report aggregate-dir``
-----------------------------

Roll up every ``*_detections.parquet`` file under a directory (e.g., the per-recording outputs of
``badc infer aggregate`` or the bundles generated via ``--bundle``) and display the busiest labels
plus recordings in one shot. This is handy after dataset-scale runs when you want a quick sanity
check across all manifests without opening DuckDB manually.

Usage::

   badc report aggregate-dir artifacts/aggregate \
       --limit 20 \
       --export-dir artifacts/aggregate/summary_exports

Behavior:

* Validates that the target directory exists and contains at least one ``*_detections.parquet`` file.
* Uses DuckDB's ``read_parquet`` globbing support to read every file at once and register a temporary
  ``detections`` view.
* Prints two Rich tables (top labels, top recordings) honoring ``--limit``.
* When ``--export-dir`` is provided, writes the tables to ``label_summary.csv`` and
  ``recording_summary.csv`` for downstream notebooks or async reviews.

Option reference
^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1

   * - Option / Argument
     - Description
     - Default
   * - ``aggregate_dir``
     - Directory containing per-recording ``*_detections.parquet`` files.
     - ``artifacts/aggregate``
   * - ``--limit INT``
     - Maximum rows per table (labels + recordings). Must be positive.
     - ``10``
   * - ``--export-dir PATH``
     - Optional directory for CSV exports (created automatically).
     - Disabled

See also
^^^^^^^^

* ``badc report bundle`` for producing each per-recording Parquet/DuckDB bundle (the rollup feeds on
  those outputs).
* ``badc infer orchestrate --bundle --bundle-rollup`` and ``badc pipeline run --bundle`` (rollup
  enabled by default) to automate the cross-run summary immediately after inference completes.
* :doc:`/howto/aggregate-results` for a walk-through that ends with this cross-run roll-up.
