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
