Apptainer Containers
====================

Sockeye requires either bare-metal modules or Apptainer/Singularity containers for complex stacks.
We package HawkEars + BADC into an Apptainer image so GPU jobs stay reproducible.

.. contents:: Topics
   :local:
   :depth: 1

Definition file
---------------
An Apptainer definition lives at ``hpc/apptainer/badc-hawkears.def``. Build from the repo root so the
``%files`` directive can stage the source tree (including submodules) into the image:

.. code-block:: singularity

   Bootstrap: docker
   From: nvidia/cuda:12.2.2-runtime-ubuntu22.04

   %labels
       Author BADC
       Description "HawkEars + BADC CLI for Sockeye GPU runs"

   %files
       ../.. /stage/badc-src

   %post
       set -euo pipefail
       export DEBIAN_FRONTEND=noninteractive
       apt-get update
       apt-get install -y --no-install-recommends \
           python3 python3-venv python3-pip \
           git ffmpeg git-annex \
           libsndfile1 \
           ca-certificates
       rm -rf /var/lib/apt/lists/*

       python3 -m venv /opt/badc/venv
       . /opt/badc/venv/bin/activate
       pip install --upgrade pip

       mkdir -p /opt/badc/src
       cp -a /stage/badc-src /opt/badc/src/repo
       cd /opt/badc/src/repo
       pip install --no-cache-dir .

       mkdir -p /opt/badc/etc

   %environment
       export PATH="/opt/badc/venv/bin:$PATH"
       export BADC_DATA_CONFIG=${BADC_DATA_CONFIG:-/opt/badc/etc/data.toml}
       export PYTHONUNBUFFERED=1

   %runscript
       exec "$@"

Build & publish
---------------
1. From repo root (with submodules checked out), run:
   ``apptainer build --fakeroot hpc/apptainer/badc-hawkears.sif hpc/apptainer/badc-hawkears.def``.
2. Store the ``.sif`` in ``/project/<pi>/containers`` or push to Sylabs/ORAS:
   ``apptainer push hpc/apptainer/badc-hawkears.sif oras://cloud.sylabs.io/<namespace>/badc-hawkears:latest``
   (or sync to Chinook object storage for Sockeye pulls).
3. Record the build command + checksum + destination in ``CHANGE_LOG.md``.

Using the container
-------------------
* On Sockeye: ``apptainer exec --nv /project/<pi>/containers/badc-hawkears.sif badc infer run ...``.
* Bind datasets explicitly if they live outside the default mount set:
  ``apptainer exec --nv --bind /project/pi-mygroup/badc/data:/data ...``.
* Keep the container under version control (definition file + notes) so we can rebuild whenever
  dependencies change.

GPU passthrough checklist
-------------------------
* Confirm the container exposes CUDA by running ``apptainer exec --nv badc-hawkears.sif nvidia-smi``.
* When binding datasets outside the default search path, add ``--bind /project/<pi>/badc/data:/data`` so HawkEars can find chunk WAVs.
* Embed ``badc gpus`` at the top of your SLURM scripts to log which devices were visible inside the container.

Integrating with DataLad
--------------------------
* Always call ``datalad run`` from the dataset root before ``apptainer exec`` so provenance records both the manifest input and ``artifacts/infer`` output.
* To keep the container immutable, mount ``/tmp`` or scratch areas as writable overlays (``--writable-tmpfs``) when HawkEars needs temporary space.
