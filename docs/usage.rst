Usage Overview
==============

The CLI entry point is ``badc``. To bootstrap a new checkout, run::

    $ git submodule update --init --recursive
    $ badc data connect bogus --pull

That clones the HawkEars fork and the bogus DataLad dataset (if `datalad` is installed) and records
the dataset path in ``~/.config/badc/data.toml``.

After bootstrapping, the CLI exposes dataset management helpers plus the initial chunking/inference
scaffolding::

    $ badc version
    BADC version: 0.1.0

    $ badc data connect bogus --path data/datalad --pull
    Updated dataset bogus at data/datalad/bogus.

    $ badc data status
    Tracked datasets:
     - bogus: connected (data/datalad/bogus)

    $ badc data disconnect bogus --drop-content
    Dataset bogus marked as disconnected; data removed.

    $ badc chunk probe data/datalad/bogus/audio/XXXX-000_20251001_093000.wav --initial-duration 120
    Probe placeholder: max chunk 120.00s for ...

    $ badc chunk manifest data/datalad/bogus/audio/XXXX-000_20251001_093000.wav --chunk-duration 60 --hash-chunks
    Wrote manifest with chunk duration 60s to chunk_manifest.csv (with hashes)

    $ badc chunk run data/datalad/bogus/audio/XXXX-000_20251001_093000.wav --chunk-duration 60 --manifest chunks.csv
    Wrote chunk files and manifest entries...

    $ badc infer run chunk_manifest.csv --runner-cmd "echo hawkears-stub"
    Processed 1 jobs; outputs stored in artifacts/infer

    $ badc infer run chunk_manifest.csv --use-hawkears --hawkears-arg --fast
    Processed 1 jobs; outputs stored in artifacts/infer

    $ badc infer run chunk_manifest.csv --cpu-workers 4
    Processed 3 jobs; outputs stored in artifacts/infer

    $ badc gpus
    Detected GPUs:
     - #0: NVIDIA Quadro RTX 4000 (8129 MiB)

    $ badc infer aggregate artifacts/infer --output artifacts/aggregate/summary.csv
    Wrote detection summary to artifacts/aggregate/summary.csv

    $ badc telemetry --log data/telemetry/infer/log.jsonl
    Telemetry records (10):
     [success] chunk_a (GPU 0) 2025-12-06T08:00:00+00:00 runtime=1.23

The commands run locally without GPU dependencies so we can test the scaffolding in CI.
