Sockeye GPU Workflow
====================

Sockeye is UBC ARC's multi-tenant GPU cluster. This page captures the conventions we use to run
HawkEars inference there without breaking cluster policies.

.. contents:: Topics
   :local:
   :depth: 1

Prerequisites
-------------
* Active Sockeye account with permission to submit GPU jobs.
* ``module load apptainer`` and ``module load cuda/<version>`` available on login nodes.
* DataLad + git-annex installed in your home or project environment (see ``notes/datalad-plan.md``).
* Data staged in a project directory (``/project/<pi>/badc``) or on the scratch filesystem; avoid
  using ``$HOME`` for large data.

Resource requests
-----------------
* GPU partitions: ``gpu`` (A100/H100 mix) and ``gpu-a40`` (A40 cards). Use ``--gres=gpu:<N>`` where
  ``N`` ≤ 4 per job.
* Typical HawkEars run: ``--time=04:00:00 --mem=64G --cpus-per-task=8`` works for four concurrent
  GPUs. Adjust according to chunk duration.
* Set ``--account=<pi-allocation>`` so the job charges the correct project.

Working with DataLad
--------------------
1. Clone the source repo (with submodules) on the login node: ``git clone --recurse-submodules``.
2. For each dataset, run ``badc data connect bogus --path /project/<pi>/badc/data/datalad`` or your
   production dataset clone. The CLI writes metadata to ``~/.config/badc/data.toml`` so future jobs
   can locate it.
3. Inside job scripts, prefer ``datalad run`` to wrap the inference command. This records provenance
   and keeps outputs inside the dataset root.

Example SLURM script
--------------------
.. code-block:: bash

   #!/bin/bash
   #SBATCH --job-name=badc-hawkears
   #SBATCH --partition=gpu
   #SBATCH --gres=gpu:4
   #SBATCH --cpus-per-task=8
   #SBATCH --mem=64G
   #SBATCH --time=04:00:00
   #SBATCH --account=pi-mygroup
   #SBATCH --output=logs/%x-%j.out

   module load apptainer/1.3 cuda/12.2
   source /project/pi-mygroup/badc/.venv/bin/activate

   DATASET=/project/pi-mygroup/badc/data/datalad/bogus
   cd "$DATASET"

   # Ensure latest audio
   datalad update --how=merge --recursive

   MANIFEST=manifests/GNWT-290.csv
   IMG=/project/pi-mygroup/containers/badc-hawkears.sif

   datalad run -m "hawkears $(basename "$MANIFEST")" \
     --input "$MANIFEST" \
     --output artifacts/infer \
     -- \
     apptainer exec --nv "$IMG" badc infer run "$MANIFEST" \
       --use-hawkears --max-gpus 4 --hawkears-arg --confidence --hawkears-arg 0.7

Automatic GPU detection
--------------------------
* Run ``badc gpus`` inside the allocation after loading modules to confirm the devices exposed via ``CUDA_VISIBLE_DEVICES`` match the ``--gres`` request.
* Limit utilization with ``--max-gpus`` when you intentionally reserve more GPUs than needed (e.g., staging pipelines or throttling HawkEars concurrency).
* CPU-only dry runs: supply ``--cpu-workers`` (>=1) and omit ``--max-gpus`` so the scheduler spins up threads even if no GPUs are detected.

Job arrays & manifests
----------------------
* Batch many manifests by storing their relative paths in a text file and launching a SLURM array::

     #SBATCH --array=1-10
     MANIFEST=$(sed -n "${SLURM_ARRAY_TASK_ID}p" manifests.txt)
     datalad run -m "hawkears $(basename "$MANIFEST")" \
       --input "$MANIFEST" --output artifacts/infer \
       -- apptainer exec --nv "$IMG" badc infer run "$MANIFEST" --use-hawkears

* Keep array jobs idempotent by writing outputs under ``artifacts/infer/<recording>/`` inside the dataset so failed tasks can be retried with ``datalad rerun``.

Telemetry & monitoring
----------------------
* Use ``badc telemetry --log data/telemetry/infer/log.jsonl`` to inspect the last few chunks.
* For real-time GPU stats, add ``nvidia-smi dmon -s pucm -i 0,1,2,3`` in a separate ``srun`` shell
  or run ``badc gpus`` at job start to confirm visibility.

Common pitfalls
---------------
* Forgetting ``module load apptainer`` causes ``exec: apptainer: not found`` errors.
* Always run ``datalad run`` from inside the dataset root; otherwise ``--print-datalad-run`` refuses
  to emit commands.
* Clean up scratch: Sockeye purges ``$SCRATCH`` periodically. Store authoritative outputs back in
  the DataLad dataset and push to Chinook/GitHub once the run finishes.
