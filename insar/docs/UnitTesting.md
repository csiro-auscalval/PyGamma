## GAMMA-INSAR Unit Testing

Running unit tests for `gamma_insar` is as simple as running `pytest` from the project directory on a supported platform (docker options below).  The test suite was written with the assumption that GAMMA is *unavailable*, but all other dependencies are required - this is suitable for testing on a wider range of systems (such as developers machines & CI testing environments which likely won't have GAMMA licenses).

As a result of this design decision, the *unit* tests only test the logic of the workflow - not the correctness of the processed data.

To run unit tests:
```BASH
cd ~/gamma_insar
source configs/activateNCI.env ~/gamma_insar_install
pytest --disable-warnings -q  # should be error free
```

Code coverage can be checked with pytest-cov. Note that running `coverage.py` alone with this repo **does not accurately record coverage results!** The `pytest-cov` tool is required to measure coverage correctly.

To measure code test coverage:

```BASH
# run tests & display coverage report at the terminal
pytest -q --disable-warnings --cov=insar

# run tests & generate an interactive HTML report
pytest -q --disable-warnings --cov-report=html --cov=insar
```

The report is saved to `coverage_html_report` in the project dir.

The unit tests may also be run on platforms which are unsupported, or do not have the dependencies installed - via docker (assuming the target platform can run docker images), please refer to the comments at the top of the `Dockerfile` for instructions on building the image and running `pytest` in that image.

### Unit testing on NCI

The Gadi system at NCI is a supported platform, and as such running unit tests is no different - simply enter/activate your installation (see [Installation on NCI](#Installation-on-NCI)) via `configs/activateNCI.env` and run `pytest` from the project directory.
