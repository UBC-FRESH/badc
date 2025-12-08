Notebook Gallery
================

These notebooks demonstrate BADC workflows using the public ``bogus`` dataset. Keep them lightweight
(≤10 MB inputs, stub inference by default) so contributors can run them on laptops or CI workers
without GPUs.

Layout overview
---------------

``chunk_probe.ipynb``
   Explore ``badc chunk probe`` / ``badc chunk split`` and visualize segment plans.
``infer_local.ipynb``
   Run ``badc infer run`` in stub mode, inspect dataset-aware outputs, and aggregate results.
``aggregate_analysis.ipynb``
   Load detection JSON/CSV/Parquet plus ``badc report quicklook`` CSV exports into pandas/DuckDB,
   then generate quick sanity plots (top labels, chunk timelines).

Execution guidelines
--------------------
* Use ``badc data connect bogus`` so manifests/audio stay inside ``data/datalad/bogus``.
* Start each notebook with reproducible bootstrap cells (``pip install -e .``, env vars, etc.).
* Mark GPU-heavy cells with ``USE_HAWKEARS`` guards or convert them into ``badc --print-datalad-run``
  snippets until we have GPU-backed CI.
* Clear outputs before committing; if we need rendered previews, export HTML copies into ``docs/``.

.. toctree::
   :maxdepth: 1

   chunk_probe
   infer_local
   aggregate_analysis
