#!/usr/bin/env python

"""
Setup gamma_insar
"""
from __future__ import absolute_import
from pathlib import Path
from setuptools import setup, find_packages

import versioneer

HERE = Path(__file__).parent

README = (HERE / "README.md").read_text()

# with open('requirements.txt') as requirement_file:
#     requirements = [r.strip() for r in requirement_file.readlines()]

setup_requirements = ["pytest-runner"]

test_requirements = [
    "pytest",
    "pytest-cov",
]

setup(
    author="The gamma insar authors ",
    author_email="earth.observation@ga.gov.au",
    python_requires=">=3.6",
    classifiers=[
        "Development Status :: 2 - Pre-Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: Apache Software License",
        "Natural Language :: English",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
    ],
    description="Sentinel-1 SLC to backscatter processing tool using GAMMA SOFTWARE",
    entry_points={
        "console_scripts": [
            "gamma_insar=insar.scripts.process_gamma:run",
            "pbs-insar=insar.scripts.insar_pbs:ard_insar",
            "pbs-package=insar.scripts.insar_pbs:ard_package",
            "package=insar.scripts.package_insar:main",
            "slc-archive=insar.scripts.grid_processing:slc_archive_cli",
            "grid-definition=insar.scripts.grid_processing:grid_definition_cli",
            "create-task-files=insar.scripts.grid_processing:create_task_files_cli",
        ],
    },
    install_requires=[
        "attrs>=17.4.0",
        "Click~=7.0",
        "GDAL>=2.4",
        "geopandas>=0.4.1",
        "luigi>=2.8.3",
        "matplotlib>=3.0.3",
        "numpy>=1.8",
        "pandas>=0.24.2",
        "pyyaml>=3.11",
        "rasterio>1,!=1.0.3.post1,!=1.0.3",  # issue with /vsizip/ reader
        "structlog>=16.1.0",
        "shapely>=1.5.13",
        "spatialist==0.4",
        "eodatasets3",
        "simplekml>=1.3.3" "",
    ],
    license="Apache Software License 2.0",
    long_description=README,
    long_description_content_type="text/markdown",
    include_package_data=True,
    keywords="gamma insar",
    name="gamma_insar",
    packages=find_packages(exclude=("tests", "tests.*")),
    package_data={"": ["*.json", "*.yaml"]},
    setup_requires=setup_requirements,
    test_suite="tests",
    tests_require=test_requirements,
    url="https://github.com/GeoscienceAustralia/gamma_insar",
    version=versioneer.get_version(),
    cmdclass=versioneer.get_cmdclass(),
)
