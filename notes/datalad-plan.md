# DataLad Repository Plan

This note tracks how BADC will manage large bird-audio assets using DataLad + UBC ARC storage. It
covers the two-tier repository approach (bogus/test vs. production) and the user-facing commands
required for connecting/disconnecting datasets at runtime.

## Goals
- Keep the Git repo lightweight while still providing representative audio samples.
- Provide an always-public "bogus" DataLad dataset (synthetic or short clips) for local dev/tests.
- Provide a production dataset that mirrors the 60 TB archive, hosted on Chinook object storage and
  gated behind UBC ARC credentials.
- Allow users to attach/detach either dataset via CLI commands so deployments can swap data sources
  without editing code.

## Repository tiers
### 1. Bogus/test dataset (public)
- **Purpose**: smoke-test chunking/inference flows, demo CLI usage, and run CI-friendly pipelines.
- **Contents**: curated short clips (≤10 MB each) plus metadata manifest. May include downsampled
  HawkEars outputs for deterministic tests.
- **Location**: GitHub repo under UBC-FRESH (e.g., `bird-audio-bogus`) initialised as a DataLad
  dataset. Storage can be plain Git (no special remotes) so contributors can clone without
  credentials.
- **Tasks**:
  - Create dataset skeleton with README describing limitations.
  - Add it as a subdataset under `data/datalad/bogus` in this repo.
- Provide automation (`scripts/datalad/setup_bogus.sh`) to clone/update it.
- Provide bootstrap script (`scripts/setup_bogus_datalad.sh`) that sources `setup/datalad_config.sh`,
  runs `datalad create`, copies the tiny audio samples, configures the GitHub remote, and executes
  `git annex initremote arbutus-s3 ...` (which creates the bucket automatically).
  - Keep file sizes below GitHub’s 100 MB limit; rely on Datalad/Git LFS only if necessary.
  - Script now understands two optional safeguards:
    - `S3_EXISTING_REMOTE_UUID` for reusing an annex bucket that was provisioned previously.
    - `S3_RESET_CONFLICTING_BUCKET=1` to instruct the script to delete/recreate buckets whose
      `git-annex-uuid` object cannot be read (otherwise it aborts with guidance).
  - **Status (2025-12-06)**: bootstrap completed successfully after clearing the conflicting
    bucket; GitHub repo `UBC-FRESH/badc-bogus-data` now exists and the Arbutus bucket was created via
    `git annex initremote`. Next step is wiring `badc data connect bogus` so contributors can clone
    `tmp/badc-bogus-data` into `data/datalad/bogus`.
  - **Submodule hook**: Added as `data/datalad/bogus` now that `UBC-FRESH/badc-bogus-data` has an
    initial commit (pushed via `datalad push`). Contributors can run `git submodule update --init`
    to fetch the bogus dataset skeleton.
  - **Caveat**: the “reuse existing bucket” path still doesn’t work reliably when the script fails
    midway (git-annex keeps seeing the orphaned `git-annex-uuid`). Until we fix the workflow, the
    only workaround after a partial failure is to delete the bucket (or at least remove its
    `git-annex-uuid` object) manually and rerun the script.

### 2. Production dataset (restricted)
- **Purpose**: house the 60 TB archive and authoritative HawkEars outputs for Erin’s project.
- **Contents**: raw WAV/FLAC shards, chunk manifests, intermediate outputs, and QA notebooks.
- **Location**: DataLad dataset backed by Chinook object storage (S3-compatible special remote).
- **Access**: restricted to PI accounts; requires UBC ARC credentials + possibly VPN.
- **Tasks**:
  - Set up the DataLad dataset on Chinook VM with `datalad create` + `datalad siblings add-s3` to
    register the special remote.
  - Document credential bootstrap (ARC tokens, environment variables, or AWS-style config files) in
    a secure note.
  - Publish dataset metadata to a GitHub repo (without annexed files) so collaborators can clone the
    structure and then `datalad get` from Chinook.
  - Define naming convention for study areas / recordings (e.g., `GNWT-290/2023/…`).
  - Determine versioning cadence (per ingest vs. per processing milestone) and record it here.

## CLI integration (`badc data connect/disconnect`)
- Implement Typer commands under the main CLI namespace:
  - `badc data connect --name bogus --path <local-path>`
    - Clones (or updates) the specified DataLad dataset into `data/datalad/<name>`.
    - Records the active dataset in a config file (e.g., `~/.config/badc/data.toml`).
  - `badc data disconnect --name bogus`
    - Drops annexed content (`datalad drop --reckless auto`) and removes the config entry.
  - `badc data status` to list attached datasets and whether their content is present locally.
- Commands should emit clear guidance when credentials are missing (production repo) or when
  detaching would remove in-use files.
- Provide optional `--special-remote` argument so advanced users can point at alternate Chinook
  buckets.
- Surface these commands in docs + README as part of environment bootstrap.
- **Status (2025-12-06)**: CLI commands now exist and write to `~/.config/badc/data.toml`; they can
  clone/update datasets via `datalad` (preferred) or plain git. The default `bogus` dataset now
  lives at `data/datalad/bogus` via a git submodule, so `badc data connect bogus` points at that
  location without extra flags.

## Open questions / follow-ups
1. How much bogus data do we need to exercise CUDA chunking without tripping GPU VRAM limits?
2. Should the production dataset include HawkEars intermediate outputs, or should those live in a
   sibling dataset to keep annex sizes manageable?
3. What is the preferred secret-management mechanism for Chinook credentials (ARC Vault, Pass,
   environment module)?
4. Do we need per-user quotas/logging when `badc data connect` pulls tens of GB onto dev servers?
5. Can we automate dataset integrity checks (e.g., `datalad fsck`) inside CI for the bogus repo?

## Installation notes
- **git-annex** is mandatory. Install via NeuroDebian/apt on Ubuntu, Homebrew on macOS, or the
  cross-platform `datalad-installer git-annex` tool (recommended when system packages lag).
- After `git-annex` is on `PATH`, install DataLad plus extras: `python -m pip install
  "datalad[full]"`. Use `--user` or `pip3` variants as needed.
- The `datalad-installer` Python package can bootstrap both `git-annex` and DataLad in a portable
  fashion, which may be easier on HPC nodes where we lack root.

## DataLad bogus dataset creation notes

We are gouing to want to set up a bogus datalad dataset with a GitHub+ArbutusS3 pattern, using the UBC-FRESH org pattern docucmneted here:

https://github.com/UBC-FRESH/lab-data-workflow-workshop/blob/main/arbutus_s3/datalad_s3_setup.md

These are similar notes below, from the UBC-FRESH org knowledge base on GitHub:

This page documents how we use **DataLad** to version-control, publish, and share large research datasets in the FRESH Lab. It includes background, rationale, challenges, solutions, and step-by-step instructions.

---

# Why DataLad?

**DataLad** builds on top of `git` and `git-annex` to enable:

- Version control of *large* files (like geospatial datasets, simulation outputs, etc.).
- Clear provenance of data transformations.
- Easy sharing with collaborators.
- Consistency with the **FAIR** principles (Findable, Accessible, Interoperable, Reproducible).

We chose DataLad because:

- A plain `git` repository cannot handle large files.
- Raw `git-annex` is very powerful but difficult to use without tooling.
- DataLad manages nested datasets, metadata, and reproducible workflows more easily.

However, DataLad doesn’t itself *host* your data--you must set up storage (e.g., S3 bucket in an Arbutus cloud project, GIN server).

Some aspirational goals for whatever DataLad solution we implement in any given project:

- Can store terabytes of files.
- Is accessible without requiring users to create accounts.
- Ideally resides in Canada (e.g.,S3 bucket in Arbutus cloud project that has object storage enabled) to meet FIPPA compliance.
- Doesn’t incur high per-GB fees.
- Fast upload and dowload speeds.
- Is simple to set up.
- Is simple to deploy.
- Is reliable and scalable (i.e., does not constantly require debugging and patching, or substantial resources allocated to regular maintenance keep working).

We have tested two basic patterns for creating and deploying DataLad datasets, which will designate *GitHub repository plus Arbutus S3 bucket* and *GIN repository*. Details follow.

---

# DataLad Project Pattern 1: GitHub repository plus Arbutus S3 bucket

This is the recommended pattern for projects that have large (i.e., 2+ Gb) total files in the project (or if you need the fastest upload and download transfer speeds, or if you need the data to be stored on a server in Canada). The pattern will not automatically result in a nice citable DOI, but you can always get a DOI with a bit of extra work if you push a copy of your dataset to an additional repository (e.g., GIN is an easy self-serve option with no gatekeepers--FRDR and Borealis[Dataverse] also generate a DOI but both have some sort of gatekeeper that you must pass before getting your DOI).     

## Structure:

- **GitHub repository** (`origin` sibling): stores lightweight dataset metadata and small files.
- **Arbutus S3 bucket** (`arbutus-s3` sibling): stores the large data content. Note 5 Gb maximum file size S3 upload file transfer limit (there are ways to get around this, but it gets a bit messy--e.g. manually split large files into multi-part ZIP files and manually re-stitch them back together after deployment, use `rclone` to manually upload large files and manually patch git annex URLs, etc). 

## Step-by-Step Instructions

Below is a workflow you can adapt.

---

### 1. Project Setup (Initial Author)

#### 1.1 Create and Activate a Virtual Environment

```bash
python -m venv .venv
pip install --upgrade pip
source .venv/bin/activate
pip install datalad[full]
```

Also install `awscli` or `s3cmd` if need to manually manipulate S3 buckets. Should not be necessary for basic deployments if you stick to the basic patterns described here.

---

#### 1.2 Create the DataLad Dataset

```bash
datalad create -c text2git my-dataset
cd my-dataset
```

---

#### 1.3 Add Data Files

```bash
mkdir data
# Copy your files into ./data
```

If you have files larger than 5GB, split them:

```bash
zip -s 4G data/large-file-split.zip large-file.gpkg
```

This creates:
- `large-file.zip`
- `large-file.z01`

Add everything:

```bash
datalad save -m "first commit"
```

---

#### 1.4 Create the Arbutus S3 bucket sibling

Create the `arbutus-s3` sibling, which automatically creates a new Arbutus S3 bucket.

```bash
git annex initremote arbutus-s3 \
  type=S3 \
  encryption=none \
  bucket=ubc-fresh-my-dataset \
  public=yes \
  publicurl=https://object-arbutus.cloud.computecanada.ca/ubc-fresh-my-dataset \
  host=object-arbutus.cloud.computecanada.ca \
  protocol=https \
  requeststyle=path \
  autoenable=true
```

Note that you will need to have valid AWS credentials defined in your environment before running the above command, because this triggers creation of a new S3 bucket in Arbutus cloud, which requires AWS credentials that map to a valid CCDB user with appropriate access permissions to a specific Arbutus cloud project in which S3 bucket object storage has been configured and enabled. 

See [Arbutus object storage](https://docs.alliancecan.ca/wiki/Arbutus_object_storage) for details on how to set this up in your account.

Assuming that you have valid AWS credentials already, the simplest way to define these in your environment is to export a pair of environment variables on the command line before running the `git annex` command above.

```bash
export AWS_SECRET_ACCESS_KEY=<AWS secret access key value>
export AWS_ACCESS_KEY_ID=<AWS access key ID value>
```

---

#### 1.5 Create the GitHub repository sibling

Create the `origin` GitHub repository sibling, which automatically creates a new public GitHub repository in the UBC-FRESH organization. Add the `--private` flag to create a private repository. The `arbutus-s3` sibling we created in the previous step is linked as a publication dependency, so large data file content will be automatically pushed to the `arbutus-s3` sibling when you push to the `origin` sibling. 


```bash
datalad create-sibling-github \
  --github-organization UBC-FRESH \
  --name origin \
  --publish-depends arbutus-s3 \
  my-dataset
```

Configure multipart threshold (not sure if this actually does anything--more testing required but does not seem to break anything either):

```bash
git config remote.arbutus-s3.annex-multipartthreshold 50M
```

---

#### 1.6 Push data to both siblings

```bash
datalad push --to origin
```

This should push metadata and any non-git-annexed filed (e.g., smaller text files, because we used `-c text2git` flag when creating the DataLad dataset). 

---

### 2. Project deployment

To clone the dataset:

```bash
datalad clone https://github.com/UBC-FRESH/my-dataset.git
cd my-dataset
```

To retrieve files:

```bash
datalad get . -r
```

If you split files, reassemble them:

```bash
zip -s 0 large-file-split.zip --out large-file.zip
unzip large-file.zip
```

---

## Notes

- **S3 upload limits:** Need to split files over 5GB.
- **Public access:** We set `public=yes` in `git annex initremote`.
- **Canadian storage:** Arbutus ensures compliance.
- **No accounts required:** Files are directly downloadable.
- **Versioning:** All changes are tracked.

---

# DataLad Project Pattern 2: GIN repository

This is the recommended pattern for projects that have smaller (i.e., less than 2 Gb) total files in the project and if you *do not* need the data to be stored on a server in Canada (the GIN server is located in Germany). This pattern *will* automatically result in a citable DOI (which is a nice feature). This is overall the simplest and cleanest pattern to set up (in many but not all aspects), because both the metadata and the data are stored in a single GIN repository on a single GIN server (as opposed to the *GitHub repository plus Arbutus S3 bucket* pattern, which splits the data between two place that then have to be correctly linked together for everything to work as intended).

Be warned that download speeds from the GIN server can be much slower than download speeds from an Arbutus S3 bucket (e.g., 0.1 Mbps from GIN server versus 30 Mbps download from Arbutus S3 bucket). This can blow up download times to the 24 hour (or more) range for very large (e.g., 10+ Gb) projects, which in practice might be an issue. For smaller projects, this should not be a problem (unless for some reason you plan to do *a lot* of repeated uploads or downloads of your DataLad dataset, which probably should not happen in practice unless you are designing your working all wrong).      

## Structure:

- **GIN repository** (`origin` sibling): stores both metadata and file content in a single repository on a single GIN server.

## Step-by-Step Instructions

Below is a workflow you can adapt.

---

### 1. Project Setup (Initial Author)

#### 1.1 Create and Activate a Virtual Environment

```bash
python -m venv .venv
pip install --upgrade pip
source .venv/bin/activate
pip install datalad[full]
```

---

#### 1.2 Create the DataLad Dataset

```bash
datalad create -c text2git my-dataset
cd my-dataset
```

---

#### 1.3 Add Data Files

```bash
mkdir data
# Copy your files into ./data
```

Add everything:

```bash
datalad save -m "first commit"
```

#### 1.5 Create the GIN repository sibling

Create the `origin` GIN repository sibling, which automatically creates a new public GIN repository in the UBC-FRESH organization. 

```bash
datalad create-sibling-gin UBC-FRESH/my-dataset -s origin
```

Note that you need to have a GIN account and be a member of the UBC-FRESH GIN organization to have permissions to create new GIN repositories on the fly like this. You will have to generate a GIN personal access token (PAT) and use this PAT to authenticate yourself the first time you try to connect to the GIN server from a new environment. You might also need to add the public half of an RSA key to your GIN account if GIN is using ssh (as opposed to https) to push and pull the files to and from the GIN server.  

---

#### 1.6 Push data to the GIN sibling

```bash
datalad push --to origin
```

This should push metadata and any git-annex files up to the GIN repository. 

---

### 2. Project deployment

To clone the dataset:

```bash
datalad clone https://gin.g-node.org/UBC-FRESH/my-dataset.git
cd my-dataset
```

To retrieve files:

```bash
datalad get . -r
```

---

## Notes

- **Public access:** GIN repository will be public access the way we set it up above, however you can set different access policies on a per-repository basis from the GIN web interface.
- **German storage:** My not comply with FIPPA or other data storage requirement in some cases.
- **No accounts required:** Files are directly downloadable.
- **Versioning:** All changes are tracked.

---


# Additional Tips (apply regardless of project implementation pattern)

- Always `datalad save` before pushing.
- Use `datalad status` to see untracked files.
- Use `git annex whereis` to verify content locations.
- For very large datasets, consider `datalad run` to record processing steps.

---


```
