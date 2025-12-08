Chunk Audio Recordings
======================

Use this guide when you need to turn long WAV recordings into inference-ready chunks across an
entire DataLad dataset.

1. **Probe a representative file** to determine safe chunk durations.

   .. code-block:: console

      $ badc chunk probe data/datalad/bogus/audio/XXXX-000_20251001_093000.wav \
          --initial-duration 60 --max-duration 600 --tolerance 5

   The command prints the recommended chunk duration and stores telemetry under
   ``artifacts/telemetry/chunk_probe/`` for posterity.

2. **Plan per-recording chunk runs** with ``badc chunk orchestrate`` (Phase 2 CLI scaffold).

   .. code-block:: console

      $ badc chunk orchestrate data/datalad/bogus \
          --pattern "*.wav" \
          --chunk-duration 60 \
          --overlap 0 \
          --manifest-dir manifests \
          --chunks-dir artifacts/chunks \
          --print-datalad-run

   The command prints a Rich table showing which recordings still need manifests and the directories
   where chunks/manifests will live. With ``--print-datalad-run`` enabled you also get copy/pastable
   commands similar to::

      datalad run -m "Chunk XXXX" \
        --input audio/XXXX.wav \
        --output artifacts/chunks/XXXX \
        --output manifests/XXXX.csv \
        -- badc chunk run audio/XXXX.wav \
             --chunk-duration 60 \
             --overlap 0 \
             --output-dir artifacts/chunks/XXXX \
             --manifest manifests/XXXX.csv

   Run each command from the dataset root to keep provenance in Git/annex.

3. **Write chunks + manifests** using ``badc chunk run`` (either manually or by reusing the command
   emitted above). If you trust the plan, append ``--apply`` to ``badc chunk orchestrate`` to run
   every chunk job automatically.

   .. code-block:: console

      $ datalad run -m "Chunk XXXX" \
          --input audio/XXXX.wav \
          --output artifacts/chunks/XXXX \
          --output manifests/XXXX.csv \
          -- badc chunk run audio/XXXX.wav \
               --chunk-duration 60 \
               --overlap 0 \
               --output-dir artifacts/chunks/XXXX \
               --manifest manifests/XXXX.csv

4. **Validate** the manifest by running ``badc chunk manifest`` or ``badc chunk split`` if you only
   need placeholders. Once chunking is complete, proceed with ``badc infer run`` as described in
   :doc:`infer-local`.

Future iterations will allow ``badc chunk orchestrate`` to execute the chunking directly when an
``--apply`` flag is set, but the planning-first workflow already accelerates multi-recording runs
while preserving DataLad provenance.
