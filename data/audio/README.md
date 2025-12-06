Sample audio files now live exclusively in the bogus DataLad dataset submodule at
`data/datalad/bogus/audio/`. Run:

```
git submodule update --init --recursive
badc data connect bogus --pull
```

to ensure the dataset is cloned and registered. Keep this directory empty in the main repo so large
WAV files remain versioned by DataLad instead of Git.
