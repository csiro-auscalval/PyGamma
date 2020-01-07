#!/usr/bin/env python3

"""
Setup gamma_insar
"""
from setuptools import setup, find_packages

import versioneer

with open('README.rst') as readme_file:
    readme = readme_file.read()

with open('HISTORY.rst') as history_file:
    history = history_file.read()

with open('requirements.txt') as requirement_file:
    requirements = [r.strip() for r in requirement_file.readlines()]

setup_requirements = ['pytest-runner']

test_requirements = ['pytest']

setup(
    author="The insar authors ",
    author_email='earth.observation@ga.gov.au',
    python_requires='>=3.5',
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: Apache Software License',
        'Natural Language :: English',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
    ],
    description="Sentinel-1 SLC to backscatter processing tool using GAMMA SOFTWARE",
    entry_points={
        'console_scripts': [
            'insar=gamma_insar.insar.scripts.process_gamma:run'
        ],
    },
    install_requires=requirements,
    license="Apache Software License 2.0",
    long_description=readme + '\n\n' + history,
    include_package_data=True,
    keywords='gamma insar',
    name='gamma_insar',
    packages=find_packages(include=['gamma_insar', 'gamma_insar.*']),
    setup_requires=setup_requirements,
    test_suite='tests',
    tests_require=test_requirements,
    url='git@github.com:GeoscienceAustralia/gamma_insar.git',
    version=versioneer.get_version(),
    cmdclass=versioneer.get_cmdclass(),
    zip_safe=False,
)
