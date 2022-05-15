## InSAR geospatial database

For large scale datasets, it's not feasible to individually pass in data acquisitions and have their data parsed every time the stack needs to start/resume/append processing data.  To this end, `gamma_insar` supports indexing data acquisitions into a geospatial temporal database which keeps a record of all the data acquisitions available, their geospatial metadata, and indexes them in a way that's optimal for the workflow to query and use.

This guide explains how to generate and maintain such a database.

#### Metadata YAML extraction

The first step in creating the database is to extract the appropriate metadata from acquisitions into a standardised format, this must be done for all acquisitions you wish to add to the database.

The archiving script currently only archives a single month at a time, specified via the `--year` and `--month` arguments.

This example extracts the SLC acquisition details for Jan 2020 into YAML files (`--save-yaml`) for a single month from a dir specified via `--slc-dir`.

```BASH
slc-archive slc-ingestion \
    --save-yaml \
    --yaml-dir /path/do/output/yaml_dir \
    --year 2020 \
    --month 01 \
    --slc-dir /g/data/fj7/Copernicus/Sentinel-1/C-SAR/SLC \  # change if required
    --log-pathname /path/do/output/yaml_dir/archive_202001.log
```

This can take anywhere from a few minutes for just a couple of scenes, up to many hours for hundreds of scenes (eg: years of S1 data).

#### Database Creation

Once the metadata has been standardised into the yaml format, it can be ingested into the database.

This example creates (or updates an existing) the database (sqlite .db) file from SLC metadata stored in the yaml files:

```BASH
slc-archive slc-ingest-yaml \
        --database-name <output-sqlite-database-filename> \
        --yaml-dir <base-dir-containing-yaml-files> \
        --log-pathname <output-json-log-filename>
```

Note: the run time can be quite long depending (over an hour) on how many yaml files there are.
