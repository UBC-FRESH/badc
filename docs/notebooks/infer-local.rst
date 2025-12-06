Local Inference Notebook
========================

This notebook will walk through running ``badc infer run`` in stub mode on the bogus dataset.

Planned sections
-----------------

1. Bootstrap (``pip install -e .``, ``badc data connect bogus``).
2. Generate/inspect a chunk manifest via ``badc chunk manifest``.
3. Execute ``badc infer run --stub-runner`` for a single manifest and inspect JSON outputs.
4. Aggregate results with ``badc infer aggregate`` and visualize detections.

Keep cells parameterized so we can toggle between stub and HawkEars modes without editing code.
