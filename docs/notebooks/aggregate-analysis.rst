Aggregate Analysis Notebook
===========================

Outline
-------

1. Load ``artifacts/infer`` JSON (or aggregated CSV) from the bogus dataset using pandas/DuckDB.
2. Demonstrate simple quality checks: number of detections per chunk, per label histograms, etc.
3. Show how to join telemetry logs to detections for runtime vs. confidence plots.
4. Export summary tables back into the DataLad dataset for sharing.

This notebook should remain GPU-agnostic and runnable via ``uv pip install notebook && jupyter lab``
on a laptop.
