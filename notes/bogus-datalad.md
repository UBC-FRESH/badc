# Bogus DataLad Dataset Plan

Purpose: provide a lightweight, public DataLad dataset containing short audio clips + metadata so
contributors can test `badc data connect`/`disconnect` without touching the 60 TB production data.

## Dataset goals (current state)
- Carry a handful of real GNWT recordings (now five clips):
  - GNWT-114_20230509_094500 (~10 chunks @ 60 s each; ~10 min)
  - GNWT-131_20230508_050402 (~60 chunks @ 60 s; ~60 min)
  - GNWT-290_20230331_235938 (~60 chunks @ 60 s; ~60 min)
  - GNWT049_20230401_010000 (~10 chunks @ 60 s; ~10 min)
  - GNWT231_20230501_072500 (~10 chunks @ 60 s; ~10 min)
- Include a README describing provenance and usage (mix of bird-rich and noise-heavy clips so
  detections/zero-hit cases are both present).
- Serve as a submodule under `data/datalad/bogus` (already in place).
- Support `datalad get`/`drop` flows and basic integrity checks (hashes).

## Workflow
1. Create GitHub repo `UBC-FRESH/badc-bogus-audio`.
2. Initialise DataLad dataset there; commit short audio files + metadata.
3. Add as git submodule here (`data/datalad/bogus`).
4. Update `badc data connect bogus` to clone/pull the dataset if missing and record status in config.
   *(Done: CLI now clones via `datalad`/`git` and stores metadata in `~/.config/badc/data.toml`.
   Submodule `data/datalad/bogus` now tracks `UBC-FRESH/badc-bogus-data`, so local clones land in the
   correct path by default.)*
5. Document steps in README + docs.
6. Provide `badc data connect bogus --path data/datalad` example; `badc data disconnect bogus`
   drops annexed content.

## Open questions
- Should we downsample the long GNWT-131/290 clips to keep clone sizes reasonable, or leave them as
  “realistic” duration fixtures (current audio >10 MB)?
- Do we also store example HawkEars outputs? (Current dataset now carries inference/aggregate
  artifacts for the five clips; we need to decide which stay permanent vs. tmp validation bundles.)
- Should we include additional noise-only samples for negative-case testing? (Current set mixes bird
  and noise; document expected detections per clip so tests can assert counts after refresh.)
