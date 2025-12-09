Track Inference with ``datalad run``
====================================

This recipe shows how to pair ``badc`` with ``datalad run`` so every HawkEars
inference is reproducible: inputs, outputs, and the exact command line end up in
the DataLad commit history.  The workflow assumes you already cloned (or
``badc data connect``-ed) a dataset such as ``data/datalad/bogus``.

.. contents:: Steps
   :local:
   :depth: 1

Prerequisites
-------------

1. DataLad + git-annex installed (see ``notes/datalad-plan.md`` for platform
   specifics).
2. A BADC checkout with Typer CLI entry points available (``pip install -e .``
   or ``uv pip install -e .``).
3. Chunk manifest CSV living *inside* the target DataLad dataset.  The manifest
   can be generated via ``badc chunk split --manifest data/datalad/bogus/...``.
4. ``badc data connect bogus`` (or your production dataset) executed so the
   local registry knows where the files reside.

Step 1 – Confirm dataset layout
-------------------------------

.. code-block:: console

   $ badc data status
   Tracked datasets:
     - bogus: connected (/home/user/projects/badc/data/datalad/bogus)

Change into the dataset root and verify DataLad metadata exists::

   $ cd data/datalad/bogus
   $ ls .datalad
   config  config.datalad  siblings.datalad

Step 2 – Generate (or locate) a chunk manifest
----------------------------------------------

Use the chunk CLI to rewrite or validate the manifest so that every chunk path
stays relative to the dataset root.  Example::

   $ badc chunk split audio/GNWT-290_20230331_235938.wav \
       --chunk-duration 60 \
       --manifest manifests/GNWT-290.csv

The manifest file now sits under the DataLad repo (``manifests/``).  This is a
requirement for ``--print-datalad-run`` to work because BADC needs to declare
``--input`` paths relative to the dataset root.

Step 3 – Ask BADC to draft the ``datalad run`` command
------------------------------------------------------

From anywhere (project root or dataset root) run::

   $ badc infer run data/datalad/bogus/manifests/GNWT-290.csv \
       --use-hawkears \
       --print-datalad-run

BADC inspects every chunk, finds the dataset root via ``badc.data.find_dataset_root``,
and emits a command similar to::

   datalad run -m "badc infer GNWT-290.csv" \
     --input manifests/GNWT-290.csv \
     --output artifacts/infer \
     -- badc infer run manifests/GNWT-290.csv --use-hawkears

Nothing executes yet—this step is a dry-run preview that guarantees the manifest
and output folder live inside the same dataset and that all relative paths are
valid.

Step 4 – Execute inside the dataset
-----------------------------------

Change to the dataset root (``cd data/datalad/bogus``) and run the suggested
command.  DataLad will:

* Materialize required inputs (via git-annex/datalad get).
* Execute ``badc infer run ...`` exactly as printed.
* Save the produced JSON/CSV files under ``artifacts/infer`` (BADC chooses this
  path automatically when it detects that chunks live inside a dataset).
* Create a commit referencing both the manifest and the resulting artifacts,
  along with the shell command recorded in ``git-annex`` metadata.

Step 5 – Push provenance + outputs
----------------------------------

After the ``datalad run`` command succeeds::

   $ datalad status
   $ datalad save -m "HawkEars inference for GNWT-290"
   $ datalad push --to origin

This pushes the new commit plus annexed output objects to the configured
special remote (S3 or GitHub, depending on the dataset).

Variant: scripting multiple manifests
-------------------------------------

When scheduling many manifests, wrap Steps 2–4 in a loop::

   for manifest in manifests/*.csv; do
       (cd data/datalad/bogus && \
        badc infer run "$manifest" --use-hawkears --print-datalad-run)
       # Copy/paste the emitted command or tee it into a shell script
   done

Alternatively, pass ``--max-gpus`` or ``--cpu-workers`` to fine-tune concurrency
(BADC still schedules at least one CPU worker automatically when GPUs are absent),
and append ``--hawkears-arg`` repeatedly to forward custom switches to the
HawkEars ``analyze.py`` entry point.

Troubleshooting
---------------

* If BADC reports that the manifest is outside the dataset root, move the file
  under the dataset (e.g., ``data/datalad/bogus/manifests``) or supply
  ``--output-dir`` so the workflow does not rely on dataset-relative paths.
* ``datalad run`` fails when outputs already exist.  Remove the previous
  ``artifacts/infer`` tree or use unique ``--output-dir`` values per run.
* To rerun without recomputing inference, call ``datalad rerun`` on the recorded
  commit; DataLad will restore the same inputs and execute the saved command.
