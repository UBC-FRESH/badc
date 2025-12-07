# Documentation Expansion Plan

Goal: deliver complete documentation coverage across back-end modules, CLI surface area, user guides, and HPC deployment playbooks so new contributors can operate BADC without reading source code. The plan below enumerates required sections, ownership, and acceptance criteria.

## Top-level structure
1. **README refresh**: high-level architecture, quick-start, feature matrix, link to published docs (https://ubc-fresh.github.io/badc/), contributor guide shortcuts.
2. **Sphinx site layout**:
   - `index.rst`: project overview + quick links.
   - `usage.rst`: CLI how-tos and examples per command group.
   - New sections:
     - `cli/*.rst` — detailed Typer command reference (chunk/data/infer/telemetry).
     - `api/*.rst` — autodoc for Python modules (`badc.chunk_writer`, `badc.hawkears_runner`, etc.).
     - `howto/*.rst` — cookbook tasks (e.g., "Connect bogus dataset", "Run HawkEars on Sockeye").
     - `hpc/*.rst` — SLURM templates, GPU sizing guidance, datalad run integration.
     - `notebooks/` gallery — Jupyter examples (chunking probe, detection aggregation, telemetry analysis).

## Coverage checklist
### CLI commands
- `badc version`, `badc gpus`, `badc telemetry`.
- Data commands: connect/disconnect/status, datalad config format, `--print-datalad-run` flow.
- Chunk commands: probe/split/manifest/run, chunk overlap behavior, manifest schema.
- Infer commands: manifest format, `--use-hawkears`, concurrency knobs, dataset-aware outputs, integration with `datalad run`.
- Aggregate commands: detection schema, CSV fields, sample outputs.

### Python API modules
- `badc.chunk_writer`: dataclasses, iterators, manifest writing.
- `badc.hawkears_runner`: structured JSON output schema, retry/backoff, telemetry fields.
- `badc.infer_scheduler`: job dataclasses, telemetry logging internals.
- `badc.data`: dataset registry, config file format, helper functions.
- `badc.telemetry`: record structure, JSONL format, loading utilities.
- Additional modules (`gpu`, `hawkears`, `aggregate`, `chunking`, etc.).
- **Docstring sweep**: ensure every public module/function/class uses detailed NumPy-style docstrings per `AGENTS.md` (summary, Parameters/Returns/Raises/Notes, units/ranges/defaults).
  Documentation effort includes writing any missing docstrings before hooking them into autodoc.

### User guides / how-tos
1. **Connecting data**: clone repo, `git submodule update`, `badc data connect bogus`, handling custom DataLad siblings.
2. **Chunking workflow**: deriving chunk manifests, storing outputs, hashing.
3. **Inference workflow**:
   - Local GPU run (dev server).
   - CPU-only stub mode (for CI).
   - Running HawkEars on Sockeye (SLURM script, env modules, data staging via DataLad, telemetry collection).
4. **Data management**: using `datalad run`, storing outputs back into dataset, provenance best practices.
5. **Aggregation + analysis**: converting HawkEars JSON to CSV/Parquet, loading into DuckDB/notebooks.
6. **Monitoring**: GPU telemetry dashboards, JSONL viewers, troubleshooting OOMs.

### Jupyter notebooks
- `notebooks/chunk_probe.ipynb`: run `badc chunk probe`, visualize results.
- `notebooks/infer_local.ipynb`: stub inference + inspection of outputs.
- `notebooks/infer_hpc.ipynb`: template showing how to orchestrate remote jobs (with markdown on submission).
- `notebooks/aggregate_analysis.ipynb`: load detection CSVs, produce simple plots/tables.

### HPC documentation
- Overview of UBC ARC resources (Chinook storage, Sockeye compute).
- Apptainer/SLURM script examples, environment module loads, multi-GPU job arrays.
- Guidance on `datalad run` within SLURM (recording container runs, retrieving outputs).

### Cross-cutting elements
- **Glossary**: define HawkEars-specific terms, dataset naming conventions, acronyms (BADC, FRESH, etc.).
- **Changelog & release notes**: expand `CHANGE_LOG.md` into a published Sphinx page.
- **API reference automation**: configure `autosummary` to generate per-module stubs.

## Delivery milestones
1. **Skeleton scaffolding (Week 1)**: Add new RST structure, stub pages, enable autosummary in `conf.py`.
2. **CLI guides (Week 2)**: Document all Typer commands with examples and `--help` output snapshots.
3. **API reference (Week 3)**: Autodoc each module, ensure docstrings (NumPy style) are present.
4. **How-to cookbook (Week 4)**: Complete the six core guides + HPC SLURM example.
5. **Notebook gallery (Week 5)**: Build notebooks, integrate via `nbsphinx` or static exports.
6. **Review & QA (Week 6)**: Link check, doc tests, ensure coverage matrix is satisfied.

## Acceptance criteria
- Every CLI command has a documented example and option table.
- Every public function/class has an autodoc entry.
- Sphinx build passes with `-W` and is published to GitHub Pages.
- README and docs both link to the Sphinx site and DataLad workflows.
- HPC appendix includes at least one SLURM script and datalad run example.

## Next actions
- ✅ Baseline CLI docs (data + chunk + infer + misc) and the datalad run how-to landed on 2025-12-06.
1. Begin the NumPy docstring sweep so `docs/api/generated/*` renders real content.
2. Expand the CLI pages with option tables/screenshots as the commands stabilize (e.g., telemetry, future aggregate helpers).
3. Flesh out the HPC/how-to sections with Sockeye/Chinook SLURM scripts, Apptainer tips, and notebook gallery links.
   - Sockeye/Chinook/Apptainer docs + the "Run inference on Sockeye" how-to are now seeded (2025-12-06); follow-up work: add Chinook credential screenshots + real container definition once it exists.

Docstring sweep progress: ``badc.chunk_writer``, ``badc.data``, ``badc.audio``, ``badc.aggregate``, ``badc.gpu``, ``badc.hawkears``, ``badc.hawkears_runner``, ``badc.infer_scheduler``, ``badc.telemetry``, ``badc.chunking``, and ``badc.cli.main`` now ship full NumPy-style docstrings. Next additions will focus on any new modules introduced by the HawkEars runner/telemetry milestones.
- Notebook gallery scaffolding landed (chunk probe, local infer, aggregate analysis) and the `.ipynb` files now live under `docs/notebooks/` so nbsphinx can publish them. Next phase is fleshing out narrative/outputs and enabling execution once GPU CI exists.
