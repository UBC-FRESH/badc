Apptainer Containers
====================

Sockeye requires either bare-metal modules or Apptainer/Singularity containers for complex stacks.
We package HawkEars + BADC into an Apptainer image so GPU jobs stay reproducible.

.. contents:: Topics
   :local:
   :depth: 1

Definition file
---------------
Create ``containers/hawkears.def`` on a development machine where you have ``apptainer build``
permissions. Example skeleton:

.. code-block:: singularity

   Bootstrap: docker
   From: nvidia/cuda:12.2.2-runtime-ubuntu22.04

   %post
       apt-get update && apt-get install -y python3 python3-venv git ffmpeg
       python3 -m venv /opt/badc
       . /opt/badc/bin/activate
       pip install --upgrade pip
       pip install datalad[full] rich typer
       pip install /src/badc  # editable install copied in during %files

   %files
       .. /home/user/projects/badc /src/badc

   %environment
       export PATH="/opt/badc/bin:$PATH"
       export BADC_DATA_CONFIG=/opt/badc/etc/data.toml

Build & publish
---------------
1. ``apptainer build --fakeroot badc-hawkears.sif containers/hawkears.def`` on a trusted builder.
2. Store the ``.sif`` in ``/project/<pi>/containers`` or push to Sylabs Cloud
   (``apptainer push badc-hawkears.sif oras://cloud.sylabs.io/...``).
3. Record the build command + checksum in ``CHANGE_LOG.md``.

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

