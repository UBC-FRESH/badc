Run Inference on Sockeye
========================

This cookbook stitches together DataLad staging, Apptainer containers, and Sockeye SLURM jobs so
you can blast through manifest-sized HawkEars runs on the cluster.

.. contents:: Steps
   :local:
   :depth: 1

Pre-flight checklist
--------------------
* Review the Sockeye HPC page for the latest partition, module, and job-array guidelines.
* Ensure the DataLad dataset is clean on Chinook before copying manifests to Sockeye (``datalad status`` should report "nothing to save").
* Run ``badc data status`` on both Chinook and Sockeye to confirm the bogus/production datasets point at the same commit.
* Capture the commands you will run (``datalad run`` invocation, ``sbatch`` submission) in ``CHANGE_LOG.md`` as soon as the batch finishes.

GPU planning
------------
* Use ``badc gpus`` inside an interactive ``srun --gres=gpu:1 --pty bash`` shell to confirm which devices will be available to the job.
* If a manifest requires fewer workers than GPUs requested, pass ``--max-gpus`` to keep HawkEars from spawning unnecessary processes while still holding the reservation for future chunks.
* Sockeye arrays: pair each array index with ``--print-datalad-run`` to log the exact ``datalad run`` command before launching the batch. Store the command string in the job log for provenance.

Notebook hand-off
-----------------
* After collecting results (step 5), launch the notebook gallery (the notebook gallery (``docs/notebooks/index``)) locally or on Chinook to visualize detection counts (``notebooks/aggregate_analysis.ipynb``) before pushing to collaborators.
* The same datasets used for inference can host derived tables—run ``badc infer aggregate`` inside the dataset, ``datalad save``, then open the notebook with ``datalad run jupyter lab`` if you need provenance for figure generation.

1. Prepare the dataset on Chinook
---------------------------------
* Clone or create the DataLad dataset in ``/project/<pi>/badc/data/datalad/<name>``.
* Populate (or update) manifests under ``manifests/`` and save with ``datalad save``.
* Push metadata + content upstream:

  .. code-block:: console

     $ datalad push --to origin
     $ datalad push --to arbutus-s3

2. Stage code + containers on Sockeye
-------------------------------------
* Clone this repo with submodules into ``/project/<pi>/badc``.
* Build (or copy) ``badc-hawkears.sif`` into ``/project/<pi>/containers``.
* Create a Python virtual environment for helper scripts (optional if container used for
  everything).

3. Draft the manifest-specific job script
-----------------------------------------

.. code-block:: bash

   #!/bin/bash
   #SBATCH --job-name=hawkears-gnwt290
   #SBATCH --partition=gpu
   #SBATCH --gres=gpu:4
   #SBATCH --cpus-per-task=8
   #SBATCH --mem=64G
   #SBATCH --time=04:00:00
   #SBATCH --output=logs/%x-%j.out

   module load apptainer/1.3 cuda/12.2
   DATASET=/project/pi-mygroup/badc/data/datalad/bogus
   MANIFEST=manifests/GNWT-290.csv
   IMG=/project/pi-mygroup/containers/badc-hawkears.sif

   cd "$DATASET"
   datalad update --how=merge --recursive

   datalad run -m "hawkears $(basename "$MANIFEST")" \
     --input "$MANIFEST" \
     --output artifacts/infer \
     -- \
    apptainer exec --nv "$IMG" badc infer run "$MANIFEST" \
      --use-hawkears --max-gpus 4 --hawkears-arg --min_score --hawkears-arg 0.7

4. Submit + monitor
-------------------
* ``sbatch job.sh``
* ``squeue -u $USER`` to watch state.
* Tail the log: ``tail -f logs/hawkears-gnwt290-<jobid>.out``.
* Inspect telemetry in real time: ``badc telemetry --log data/telemetry/infer/log.jsonl`` (from the
  dataset root).

5. Collect results
------------------
* Once the job finishes, verify new JSON appears under ``artifacts/infer/<recording>/``.
* Run aggregation locally or as a follow-up job:

  .. code-block:: console

     $ badc infer aggregate artifacts/infer --output artifacts/aggregate/summary.csv
     $ datalad save -m "Aggregate GNWT-290 Sockeye run"

6. Push back to Chinook/GitHub
------------------------------
* From the dataset root:

  .. code-block:: console

     $ datalad push --to origin
     $ datalad push --to arbutus-s3

* Update ``CHANGE_LOG.md`` with the commands executed.

Troubleshooting
---------------
* ``apptainer exec`` fails with ``failed to communicate with slurmstepd`` – make sure you request
  GPUs via ``--gres`` and include ``--nv``.
* DataLad complains about dirty worktree – ensure ``datalad run`` executes inside the dataset root
  and that your manifest path is relative to that directory.
* GPU count mismatch – Sockeye injects ``CUDA_VISIBLE_DEVICES``. Let BADC detect GPUs automatically
  (default) or pass ``--max-gpus`` explicitly to stay within the allocation.
