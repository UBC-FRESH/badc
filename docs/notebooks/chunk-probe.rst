Chunk Probe Notebook
====================

A future notebook will demonstrate how to:

1. Call ``badc chunk probe`` against ``data/datalad/bogus/audio/GNWT-290_20230331_235938.wav``.
2. Visualize candidate chunk durations and overlaps with matplotlib or plotly.
3. Save the resulting manifest preview alongside telemetry notes so Sockeye jobs can reuse them.

Guidelines
----------

* Keep runtime < 2 minutes using small audio slices.
* Avoid committing generated WAVs—store them under the DataLad dataset and reference via relative
  paths.
* Clear notebook outputs before committing.
