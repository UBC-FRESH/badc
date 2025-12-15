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


## Erin's Workflow Notes: Data format, directory structures, and HawkEars processing objective

Overall objective: Process raw acoustic files in HawkEars to obtain species detections and confidence scores


- Raw acoustic data: either .wav or .flac  acoustic files
- Directory structures (vary by study area)
	- Fort Smith data directory structure: StudyAreaName/ARU_data/SM/StationName/A/Data/acousticfiles.wav
		- StationName folders have subfolders A and B, both of which contain Data folders with acoustic files
	- ThaideneNene and NormanWells data directory structure: StudyAreaName/SubdirectoryA/StationName/acousticfiles.wav
		- 'SubdirectoryA' is ARUType for NormanWells - BarLT and SongMeter - and TDN2022-01 and 02 for TDN
	- Gameti and Edehzhie data directory structure: StudyAreaName/StationName/acousticfiles.wav
	- Sambaa K'e WR 2018 and 2022 data has more complicated directory structure (based on chunks for data transfer - see README file) - simplify in upload to Chinook?
- Each study area directory might have other csv or text files - HawkEars only needs the acoustic files (.wav or .flac)
- Data to be extracted from file path: StudyAreaName (e.g., FortSmith2022), StationName (e.g., SRL-308-095-03)
- Data to be extracted from acoustic file name: date (format YYYYMMDD), time (format HHMMSS)
	- Fort Smith data has sensor ID in the file name, Sambaa K'e and Thaidene Nene have station name. Station name is what's important
	- Samba K'e files also have '0+1' between the station name and date. Not sure what this is but I don't think it's necessary
- Test HawkEars performance on target species - Can do this with WildTrax data, since they've been processed both manually and by HawkEars AND BirdNET
	- still figuring out workflow for this - some of it will be manual (requires listening to recordings)

- Datasets need to be transferred onto Chinook to access with UBC servers
- HawkEars processing: use HawkEars python script to run automated species classification
	- Target species (common names used in WildTrax reports): "Rock Ptarmigan", "Ruffed Grouse", "Sharp-tailed Grouse", "Spruce Grouse", "Willow Ptarmigan"
	- Target species (species codes used in HawkEars): ROPT, RUGR, STGR, SPGR, WIPT
	- Arguments for HawkEars script:
		- -i filepath for acoustic files (in however large a chunk of data can be processed at once)
		- -o filepath for output csv files (all files for single study area can go in one folder, though I might want sub-folders for each station?)
		- --recurse (only use if input filepath contains sub-directories)
		- --rtype csv (want output files to be CSVs)
		- --region "CA-NT" (specifies species in the Northwest Territories)
	- HawkEars output consists of a single csv file for each job processed (though if text file output is selected then there is a text file for each acoustic file) 
		- HawkEars output fields:
			- filename (name of acoustic file)
			- start_time (time in seconds the detected vocalization begins within the recording)
			- end_time (time in seconds the detected vocalization ends)
			- class_name (species common name)
			- class_code (species code)
			- score (confidence code)
	- Additional fields to be added to each CSV (data extracted from directory filepath or acoustic file name):
		- study_area
		- location
		- recording_date_time
			
	- CSV outputs need to be merged together into a single CSV file for each study area (ideally all study areas together in one as a final data product)
		- Will add station coordinates later - some of these need to be inspected and fixed


