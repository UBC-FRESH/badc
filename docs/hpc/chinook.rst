Chinook Storage Strategy
==========================

Chinook provides the object storage backend (Arbutus S3) and long-term POSIX space for BADC data.
Use it to host DataLad datasets, Apptainer images, and large inference outputs.

.. contents:: Topics
   :local:
   :depth: 1

S3 special remote
-----------------
* We follow the "GitHub metadata + Arbutus S3 content" pattern documented in
  ``notes/datalad-plan.md``.
* Configure credentials via ``setup/datalad_config.sh`` (ignored by git). Required variables:
  ``AWS_ACCESS_KEY_ID``, ``AWS_SECRET_ACCESS_KEY``, ``S3_ENDPOINT_URL``, ``S3_BUCKET_NAME``,
  ``GITHUB_ORG``, ``GITHUB_REPO_NAME``.
* The bootstrap script ``scripts/setup_bogus_datalad.sh`` demonstrates how to:
  1. ``datalad create`` the dataset.
  2. Copy audio fixtures into ``audio/``.
  3. Run ``git annex initremote arbutus-s3 ...`` which creates the bucket automatically.
  4. ``datalad create-sibling-github`` to publish the metadata repo.
* If the script fails after creating the bucket, delete the bucket (or its ``git-annex-uuid`` object)
  manually before rerunning; reuse support is still fragile.

POSIX workspace layout
----------------------
* Keep source repo, virtual environments, and containers under ``/project/<pi>/badc`` so Sockeye and
  Chinook share paths.
* Store large artifacts (e.g., aggregated CSVs) under ``/data/<pi>/badc`` if you need higher
  quotas; symlink them back into the DataLad dataset when saving commits.

Dataset lifecycle example
---------------------------
1. On your workstation, prepare manifests and telemetry folders under ``data/datalad/<name>``.
2. ``datalad save`` to capture the changes locally, then ``datalad push --to origin`` (GitHub metadata).
3. From Chinook, run ``datalad update --how=merge`` followed by ``datalad get`` for any new audio/manifest paths.
4. After Sockeye jobs finish and push artifacts back (see the "Run Inference on Sockeye" how-to), execute ``datalad push --to arbutus-s3`` on Chinook to ensure annexed WAVs land in the bucket.
5. Record the sync in ``CHANGE_LOG.md`` so collaborators understand which dataset revision reached Chinook.

Publishing changes
------------------
1. Stage work in the dataset: ``datalad save -m "Add GNWT-290 chunks"``.
2. Push metadata to GitHub: ``datalad push --to origin``.
3. Push annexed content to Chinook: ``datalad push --to arbutus-s3``.
4. Record the commands in ``CHANGE_LOG.md`` per ``AGENTS.md``.

Credential rotation
--------------------
* Store AWS/GitHub tokens in ``setup/datalad_config.sh`` and source it before running the helper scripts.
* When rotating credentials, issue ``datalad siblings configure --name arbutus-s3 ...`` to update stored access keys without recreating the dataset.
* Validate connectivity with ``git annex testremote arbutus-s3`` before launching large transfers.

Credential hygiene
------------------
* Never commit ``setup/datalad_config.sh``; the filename is already gitignored.
* When sharing instructions, reference environment variables rather than pasting secrets.
* On Sockeye, export the same variables in ``~/.bashrc`` or ``~/.bash_profile`` if the job needs to
  talk to Chinook directly (e.g., ``datalad push --to arbutus-s3`` inside a batch script).
