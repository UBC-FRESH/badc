Miscellaneous Commands
======================

These helpers surface project metadata and quick diagnostics that complement the major chunk/infer
sub-commands.

.. contents:: On this page
   :local:
   :depth: 1

``badc version``
~~~~~~~~~~~~~~~~~~~~

Print the installed package version (``badc.__version__``).

Usage::

   badc version

Typical output:

.. code-block:: console

   ─────────────────── Bird Acoustic Data Compiler ───────────────────
   BADC version: 0.1.0

``badc gpus``
~~~~~~~~~~~~~~~~

Report GPUs visible via ``nvidia-smi``. The command is a thin wrapper around ``badc.gpu.detect_gpus``
so its output mirrors what the inference scheduler will see.

Usage::

   badc gpus

Sample output::

   Detected GPUs:
    - #0: NVIDIA A100-SXM4-80GB (81251 MiB)
    - #1: NVIDIA A100-SXM4-80GB (81251 MiB)

Troubleshooting:

* If the list is empty, confirm ``nvidia-smi`` exists on ``PATH`` and the container/VM exposes GPUs.
* On CPU-only nodes, use ``badc infer run --cpu-workers`` to bypass GPU detection entirely.

Help excerpt
^^^^^^^^^^^^

.. code-block:: console

   $ badc gpus --help
   Usage: badc gpus [OPTIONS]
     Display GPU inventory as reported by `nvidia-smi`.
   Options:
     --help  Show this message and exit.

``badc telemetry``
~~~~~~~~~~~~~~~~~~~~~~~~

Tail the most recent telemetry entries (defaults to ``data/telemetry/infer/log.jsonl``).

Usage::

   badc telemetry [--log PATH]

Option reference
^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1

   * - Option / Argument
     - Description
     - Default
   * - ``--log PATH``
     - Telemetry JSONL to read (supports arbitrary pipelines).
     - ``data/telemetry/infer/log.jsonl``

Help excerpt
^^^^^^^^^^^^

.. code-block:: console

   $ badc telemetry --help
   Usage: badc telemetry [OPTIONS]
     Print the most recent telemetry records for quick inspection.
   Options:
     --log PATH  Telemetry log path.  [default: data/telemetry/infer/log.jsonl]
     --help      Show this message and exit.

Each line prints status, chunk id, GPU index, timestamp, and runtime seconds. Example::

   Telemetry records (3):
   [success] GNWT-290_chunk_1 (GPU 0) 2025-12-06T18:22:11 runtime=12.4

Use this command when monitoring SLURM jobs or local batches to confirm progress without opening the
JSONL file manually. Point ``--log`` at alternate telemetry files (e.g., chunking or aggregation
pipelines) as those land.
