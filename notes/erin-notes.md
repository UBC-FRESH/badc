# Notes for Erin Tattersall PhD project bird audio data processing

In this project we will create a framework that uses a forked (modified version) of the HawkEars software to process 60 TB of bird audio recordings, to detect the data-time stamp of bird calls from various study areas. 

We will embed the forked HarkEars github repo as as git submodule inside this project (because we might need to further modify the forked code to get it to work exactly the way we need and want it to). The fork wraps the core original software package to implement new Typer-based CLI interface and Python API bindings. 

HawkEars includes a trained ML vector machine that can perform inference operations on input audio files. It is capable of leveraging CUDA cores in an NVIDIA GPU if one is available in the target environment. The current environment has two NVIDIA Quadro RTX 4000 GPUs, which are relatively small by current ML GPU research project standards but nonetheless includes some CUDA cores (so we should be able to test the full target workflow). Early tests show that HawkEars fails with an "out of CUDA memory" error when we feed it audio input files that are too large. So, we will need to include functions in this project that automate the process of finding the maximum length of audio that HawkEars can handle inside the target environment (while can vary depending on what GPUs are available), likely by trial and error unless we can find some notes in HarkEars tech docs that let us figure that out by analysis instead of trial and error. Once we figure out the maximum "input audio chunk size", we will need to chop up all target audio input files into feasible sized chunks (staged in a temp directory), push these through the wrapped (embedded) HawkEarks slave module, collect the raw output in another temp directory, parse the raw output and an stuff it into a single output "database" (any tabular data format---we can discuss target format options later), and then so some sort of post-hoc statiscal analysis or aggregation or other data munging or tranformation on the parsed output database (details TBD---whatever the student says they need to stuff into their thesis: tables, figures, etc.). 

60 TB of data is a lot, and the GPUs on this dev server are pro-grade but relatively weak. We have access to PI accounts on UBC ARC Chinook (research data server) and Sockeye (HPC cluster). So, we might need to isolate the HawkEarks data processing module of this project so we can push the data through several of the the (many!) GPU-enabled nodes on Sockeye (which have much more powerful NVIDIA GPUs than we do in the dev server). This might require us to wrap the data-processing HawkEars module in an Apptainer container (because software stacks with complex deps can be challenging to bundle in a way that runs correctly on HPC compute nodes if one or more deps leans on system libraries that do not match the versions installed on the cluster, etc.). So, we might need to have a whole other module in this project dedicated to creating the Apptainer container (which requires a linux machine with admin permissions, which we have on the dev server), and then functions to automate pushing the container image up to the Sylabs cloud container library (from whence we can pull it back down into the HPC cluster) or maybe there is a way to directly push the container to our Chinook object storage account which has super face download speeds to Sockeye.

https://cloud.sylabs.io/library

The forked HawkEars repo:

https://github.com/UBC-FRESH/HawkEars

HawkEars web site:

https://wildlabs.net/article/hawkears-high-performance-bird-sound-classifier-canada

We have included two long)ish) audio recordings in the `data/datalad/bogus/audio/` directory (7
minutes, and 60 minutes) via the bogus DataLad dataset. The shorter one might go through HawkEars
without crashing on the dev server, but the longer one is confirmed to be too long. We ran some quick
tests earlier, and 1 minutes is OK but 10 minutes is too long. The shorter audio file has ruffed
grouse sounds (allegedly), but the longer file is maybe just a bunch of noises but no grouse (confirm).

## Coding agent contract

We will use a coding agent to help code this project. The agent will always respect the policies ("contract") in `AGENTS.md` and `CONTRIBUTING.md` (use the project files from FHOPS as a template for setting up these contracts).

## Interface and Documentation

We will publish full detailed user-facing documentation on using Sphinx, which we will publish on GitHub Pages using a CI hook on git push. The coding agent will keep all documentation up to date at each dev iteration. 

We will include both Typer-based CLI and Python API user-facing interfaces.

https://github.com/UBC-FRESH/fhops

## Packages structure

This package will use a modular design, and be designed to be extensible and reusable in future projects (not a top priority, but still generality and deployment still important to consider when making design choices).

## DataLad data management

We will use Datalad to manage the large data collection, using my 100 TB Chinook PI account (which has S3 bucket storage enabled) as the cloud storage "special remote" backend for the datalad git repo, and a github project in my UBC-FRESH GitHub org for the git metadata part. 

Links below to UBC ARC Chinook and Sockeye system descriptions and documentation, for reference.

https://arc.ubc.ca/compute-storage/ubc-arc-chinook

https://arc.ubc.ca/compute-storage/ubc-arc-sockeye

There is extensive technical documentation for these HPC resources here

https://confluence.it.ubc.ca/spaces/UARC/pages/168841652/UBC+ARC+Technical+User+Documentation

but it is hidden behind a UBC CWL login (I can access as needed and paste snippets into notes documents).
