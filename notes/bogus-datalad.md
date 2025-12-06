# Bogus DataLad Dataset Plan

Purpose: provide a lightweight, public DataLad dataset containing short audio clips + metadata so
contributors can test `badc data connect`/`disconnect` without touching the 60 TB production data.

## Dataset goals
- Contain ≤10 MB of audio (downsampled versions of `data/audio/GNWT-290_...` and
  `data/audio/XXXX-...`).
- Include a README describing provenance and usage (grouse vs. no-hit cases).
- Serve as a submodule under `data/datalad/bogus`.
- Support `datalad get`/`drop` flows and basic integrity checks (hashes).

## Workflow
1. Create GitHub repo `UBC-FRESH/badc-bogus-audio`.
2. Initialise DataLad dataset there; commit short audio files + metadata.
3. Add as git submodule here (`data/datalad/bogus`).
4. Update `badc data connect bogus` to clone/pull the dataset if missing and record status in config.
5. Document steps in README + docs.

## Open questions
- How to automate downsampling (FFmpeg scripts) to keep <10 MB?
- Do we also store example HawkEars outputs?
- Should we include noise-only samples for negative-case testing?
