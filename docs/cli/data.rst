Data Repository Commands
========================

The ``badc data`` namespace abstracts how users clone, update, and detach
DataLad-backed repositories that hold primary bird audio.  It mirrors the
practices captured in ``notes/datalad-plan.md`` and stores the results in a
small TOML registry so other tools (chunking, inference, notebooks) know where
those datasets live.

.. contents:: On this page
   :local:
   :depth: 1

Overview
--------

* Runs happily inside a virtual environment without elevating privileges.
* Supports both ``git`` and ``datalad`` clone flows—BADC auto-detects which tool
  is available unless ``--method`` forces a choice.
* Records every connected dataset in a per-user config file
  (``~/.config/badc/data.toml`` by default, override via
  ``BADC_DATA_CONFIG``).
* Knows about the ``bogus`` dataset out of the box so people can smoke-test the
  CLI without touching production remotes.  You can override the URL via
  ``--url`` for custom mirrors or private deployments.

Dataset registry
----------------

Each successful ``connect`` run (without ``--dry-run``) writes an entry that
looks like this::

   [datasets.bogus]
   path = "/home/user/projects/badc/data/datalad/bogus"
   url = "https://github.com/UBC-FRESH/badc-bogus-data.git"
   method = "datalad"
   status = "connected"
   last_connected = "2025-01-12T21:07:14.889192+00:00"

You can point BADC at an alternate config file by exporting
``BADC_DATA_CONFIG=/path/to/custom.toml`` before invoking the CLI.  That is
handy when staging datasets on different filesystems (e.g., NVMe for inference,
Ceph for archiving) or when running automated tests that should not touch the
real registry.

``badc data connect``
~~~~~~~~~~~~~~~~~~~~~

Clone (or refresh) a dataset under ``data/datalad/<name>`` and track it in the
registry.  The command returns immediately after the clone completes or after a
pull, so you can chain it inside scripts or ``datalad run`` records.

Usage::

   badc data connect NAME [--path PATH] [--url URL] [--method git|datalad]
                        [--pull / --no-pull] [--dry-run]

Key options:

``NAME``
   Dataset identifier.  ``bogus`` resolves to the public sample repository
   maintained for this project.  Unknown names require ``--url``.
``--path``
   Base directory that will hold dataset folders.  Defaults to
   ``data/datalad`` relative to the current working tree.
``--url``
   Override the clone URL.  Required when ``NAME`` is not in the built-in table
   defined in ``badc.data.DEFAULT_DATASETS``.
``--method``
   Force ``git`` or ``datalad``.  When omitted, BADC prefers ``datalad`` if the
   binary is on ``PATH`` and falls back to ``git`` otherwise.
``--pull / --no-pull``
   Controls what happens when the target directory already exists.  ``--pull``
   (default) merges upstream changes; ``--no-pull`` simply confirms the
   presence of the dataset.
``--dry-run``
   Print what would happen without touching the filesystem.

Option reference
^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1

   * - Option / Argument
     - Description
     - Default
   * - ``NAME``
     - Dataset registry key (``bogus`` built-in).
     - Required
   * - ``--path PATH``
     - Base directory where datasets are created/updated.
     - ``data/datalad``
   * - ``--url URL``
     - Override clone URL for custom/private datasets.
     - Registry value or required for unknown names
   * - ``--method git|datalad``
     - Force clone implementation. Auto-detected when omitted.
     - Auto
   * - ``--pull`` / ``--no-pull``
     - Update an existing dataset after verifying it exists.
     - ``--pull``
   * - ``--dry-run``
     - Print planned actions without touching disk or the registry.
     - Disabled

Examples::

   # Clone the public bogus dataset using DataLad (auto-detected)
   badc data connect bogus

   # Clone into a scratch filesystem and skip pulling if it already exists
   badc data connect bogus --path /mnt/scratch/badc --no-pull

   # Register a private repository
   badc data connect sockeye-prod --url git@github.com:UBC-FRESH/badc-prod-data.git

``badc data disconnect``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Remove a dataset from the active registry and optionally delete its contents.
The command never deletes anything unless you pass ``--drop-content``—that flag
is the moral equivalent of ``datalad drop --recursive``.

Usage::

   badc data disconnect NAME [--drop-content / --keep-content]
                          [--path PATH] [--dry-run]

``--drop-content``
   Recursively delete the dataset directory after marking it as disconnected.
``--path``
   Fallback search root when the dataset is not in the registry, useful for
   first-time disconnects or misconfigured machines.
``--dry-run``
   Preview the deletion/recording steps without touching the filesystem.

Option reference
^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1

   * - Option / Argument
     - Description
     - Default
   * - ``NAME``
     - Dataset identifier to mark as disconnected.
     - Required
   * - ``--drop-content`` / ``--keep-content``
     - Remove dataset files after recording the disconnection.
     - ``--keep-content``
   * - ``--path PATH``
     - Base directory to search when the registry entry is missing.
     - ``data/datalad``
   * - ``--dry-run``
     - Emit the pending actions without deleting or editing files.
     - Disabled

The registry retains the last known path and timestamp so future ``connect``
operations can reconcile state when pointed at the same location.

``badc data status``
~~~~~~~~~~~~~~~~~~~~~~

Display the tracked datasets, their status (connected or disconnected), and the
recorded filesystem paths.  Example output::

   $ badc data status
   Tracked datasets:
    - bogus: connected (/home/gep/projects/badc/data/datalad/bogus)

Option reference
^^^^^^^^^^^^^^^^

This command currently has no flags—just pass ``badc data status`` to inspect the registry.

Help excerpt
^^^^^^^^^^^^

.. code-block:: console

   $ badc data status --help
   Usage: badc data status [OPTIONS]
     Report all datasets tracked in ~/.config/badc/data.toml.
   Options:
     --help  Show this message and exit.

Use this command while debugging ``datalad run`` pipelines or before chaining a
chunk/infer workflow to confirm that the referenced repositories exist locally.

Automation tips
---------------

* Combine ``badc data connect`` with ``git submodule update --init --recursive``
  in bootstrap scripts so cloned worktrees always have both the source tree and
  the audio datasets they require.
* When integrating with ``datalad run``, call ``badc data connect`` as the first
  recorded action so downstream provenance captures the origin of the dataset.
* Emit ``badc data status`` as part of telemetry bundles to help future readers
  understand which repository revision supplied the raw WAV files.
