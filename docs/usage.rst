Usage Overview
==============

The CLI entry point is ``badc``. Today it exposes a placeholder ``version`` command and a
``data`` namespace that will eventually orchestrate DataLad datasets. Early chunking helpers are
also available::

    $ badc version
    BADC version: 0.1.0

    $ badc data connect bogus
    TODO: implement DataLad clone/register logic.

    $ badc chunk probe data/audio/XXXX-000_20251001_093000.wav --initial-duration 120
    Probe placeholder: max chunk 120.00s for ...

    $ badc infer run chunk_a chunk_b
    Inference placeholder complete:
     - chunk_a_detected

    $ badc chunk manifest data/audio/XXXX-000_20251001_093000.wav --chunk-duration 60 --hash-chunks
    Wrote manifest with chunk duration 60s to chunk_manifest.csv (with hashes)

    $ badc infer run chunk_manifest.csv --runner-cmd "echo hawkears-stub"
    Processed 1 jobs; outputs stored in artifacts/infer

    $ badc gpus
    Detected GPUs:
     - #0: NVIDIA Quadro RTX 4000 (8129 MiB)

    $ badc data connect bogus --path data/datalad
    TODO: implement DataLad clone/register logic (target repo: UBC-FRESH/badc-bogus-audio).

    $ badc infer aggregate artifacts/infer --output artifacts/aggregate/summary.csv
    Wrote detection summary to artifacts/aggregate/summary.csv

    $ badc telemetry --log data/telemetry/infer/log.jsonl
    Telemetry records (10):
     [success] chunk_a (GPU 0) 2025-12-06T08:00:00+00:00 runtime=1.23

The commands run locally without GPU dependencies so we can test the scaffolding in CI.
