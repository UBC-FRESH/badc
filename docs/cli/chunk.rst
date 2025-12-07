Chunk Commands
==============

Chunking turns long WAV recordings into short, inference-ready snippets. The ``badc chunk``
sub-commands handle estimation, manifest creation, and optional file writing while keeping metadata
compatible with the HawkEars runner.

.. contents:: On this page
   :local:
   :depth: 1

Overview
--------

* All commands operate on local WAV files (usually stored inside a DataLad dataset).
* Manifests are CSV files consumed by ``badc infer run``. Columns:

  - ``chunk_id`` – unique identifier (``<stem>_<index>`` placeholder for now).
  - ``path`` – path to the WAV chunk (absolute unless chunks live inside a dataset).
  - ``start_ms`` / ``end_ms`` – millisecond offsets relative to the source file.
  - ``overlap_ms`` – overlap applied while splitting (0 for non-overlapping chunks).
  - ``sha256`` – optional checksum (full-file hash today; per-chunk hashing planned).

``badc chunk probe``
--------------------

Quickly tests whether the requested chunk duration is viable.

Usage::

   badc chunk probe AUDIO.wav [--initial-duration SECONDS]

* Reads file metadata via ``badc.chunking.probe_chunk_duration``.
* Returns the maximum supported duration and notes (placeholder implementation today).
* Use this before launching a large split to avoid creating millions of tiny files.

Option reference
^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1

   * - Option / Argument
     - Description
     - Default
   * - ``AUDIO.wav``
     - Path to the source WAV file to probe.
     - Required
   * - ``--initial-duration SECONDS``
     - Starting chunk duration (seconds) passed to ``probe_chunk_duration``.
     - ``60``

Help excerpt
^^^^^^^^^^^^

.. code-block:: console

   $ badc chunk probe --help
   Usage: badc chunk probe [OPTIONS] FILE
     Estimate chunk duration feasibility for a single audio file.
   Arguments:
     FILE  Path to audio file to probe.  [required]
   Options:
     --initial-duration FLOAT  Starting chunk duration in seconds.  [default: 60]
     --help                    Show this message and exit.

``badc chunk split``
--------------------

Plans chunk IDs without writing files—handy for spot checks or when chunking will happen elsewhere.

Usage::

   badc chunk split AUDIO.wav --chunk-duration 45 --manifest manifests/AUDIO.csv

Options:

``--chunk-duration`` (required)
   Length of each chunk in seconds.
``--manifest``
   Output CSV path (defaults to ``chunk_manifest.csv`` in the CWD).

The command prints each placeholder ``chunk_id`` so you can inspect numbering or feed the IDs into a
separate pipeline. Because this mode does not write WAV files, it is safe to run on laptops.

Option reference
^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1

   * - Option / Argument
     - Description
     - Default
   * - ``AUDIO.wav``
     - Source WAV file to inspect.
     - Required
   * - ``--chunk-duration SECONDS``
     - Length of each planned chunk.
     - Required
   * - ``--manifest PATH``
     - Manifest path (written even though the command only emits IDs).
     - ``chunk_manifest.csv``

Help excerpt
^^^^^^^^^^^^

.. code-block:: console

   $ badc chunk split --help
   Usage: badc chunk split [OPTIONS] FILE
     List placeholder chunk identifiers for an audio file.
   Arguments:
     FILE  Path to audio file to plan splits for.  [required]
   Options:
     --chunk-duration FLOAT  Desired chunk duration in seconds.  [default: 60]
     --help                  Show this message and exit.

``badc chunk manifest``
-----------------------

Generates a manifest with optional hashing. This is the canonical entry point when you already have
chunk WAVs elsewhere (e.g., produced by a notebook or another cluster).

Usage::

   badc chunk manifest AUDIO.wav --chunk-duration 60 --output manifests/AUDIO.csv \
       [--hash-chunks]

``--hash-chunks`` recomputes SHA256 values; leave it disabled for quick iterations. The manifest CSV
is compatible with ``badc infer run`` and downstream aggregation.

Option reference
^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1

   * - Option / Argument
     - Description
     - Default
   * - ``AUDIO.wav``
     - Source WAV used to derive duration metadata.
     - Required
   * - ``--chunk-duration SECONDS``
     - Target chunk length.
     - ``60``
   * - ``--output PATH``
     - Destination manifest CSV.
     - ``chunk_manifest.csv``
   * - ``--hash-chunks`` / ``--no-hash-chunks``
     - Toggle SHA256 hashing for each manifest row.
     - ``--no-hash-chunks``

Help excerpt
^^^^^^^^^^^^

.. code-block:: console

   $ badc chunk manifest --help
   Usage: badc chunk manifest [OPTIONS] FILE
     Create a manifest CSV describing fixed-duration chunks.
   Arguments:
     FILE  Audio file to manifest.  [required]
   Options:
     --chunk-duration FLOAT  Chunk duration in seconds.  [default: 60]
     --output FILE           Output CSV path.  [default: chunk_manifest.csv]
     --hash-chunks / --no-hash-chunks
                             Toggle SHA256 hashing for each manifest row.
     --help                  Show this message and exit.

``badc chunk run``
------------------

Creates chunk WAVs and a manifest in one shot.

Usage::

   badc chunk run AUDIO.wav --chunk-duration 60 --overlap 5 \
       --output-dir artifacts/chunks --manifest manifests/AUDIO.csv

Key behaviors:

* When ``--dry-run`` is set, no files are written; BADC still reports where chunks would land.
* ``--overlap`` applies a sliding window overlap (in seconds) for edge-sensitive detectors.
* ``--output-dir`` defaults to ``artifacts/chunks`` relative to the current working tree, but when
  the source file lives in a DataLad dataset you should place this directory inside the dataset so
  ``datalad run`` can track provenance.

After chunking, the command prints the manifest path plus whether chunks were written or skipped.

Option reference
^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1

   * - Option / Argument
     - Description
     - Default
   * - ``AUDIO.wav``
     - Source WAV to split into fixed-length files.
     - Required
   * - ``--chunk-duration SECONDS``
     - Chunk length (seconds). Determines chunk count and manifest offsets.
     - Required
   * - ``--overlap SECONDS``
     - Sliding window overlap between consecutive chunks.
     - ``0``
   * - ``--output-dir PATH``
     - Directory that will contain generated chunk WAVs.
     - ``artifacts/chunks``
   * - ``--manifest PATH``
     - Manifest CSV destination.
     - ``chunk_manifest.csv``
   * - ``--dry-run`` / ``--write-chunks``
     - Skip writing WAVs and emit mock metadata when ``--dry-run`` is set.
     - ``--write-chunks``

Help excerpt
^^^^^^^^^^^^

.. code-block:: console

   $ badc chunk run --help
   Usage: badc chunk run [OPTIONS] FILE
     Write chunk WAVs (optional) and a manifest for downstream inference.
   Arguments:
     FILE  Audio file to chunk.  [required]
   Options:
     --chunk-duration FLOAT  Chunk duration in seconds.  [required]
     --overlap FLOAT         Overlap between chunks in seconds.  [default: 0]
     --output-dir PATH       Directory for chunk files.  [default: artifacts/chunks]
     --manifest PATH         Manifest CSV path.  [default: chunk_manifest.csv]
     --dry-run / --write-chunks
                             Skip writing chunk files.  [default: write-chunks]
     --help                  Show this message and exit.

Automation tips
---------------

* Record chunking steps with ``datalad run`` or ``git commit`` before launching inference so others
  know exactly how the manifest was produced.
* Store manifests near the source audio (e.g., ``data/datalad/bogus/manifests``) to keep
  dataset-relative paths intact.
* Large jobs: combine ``badc chunk run`` with GNU Parallel or SLURM array jobs by looping over
  source WAV files and writing per-file manifests under a shared folder.
