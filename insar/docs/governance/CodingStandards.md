# Coding Standards #

The `gamma_insar` project tries to keep coding standards pretty simple:
1. We stick to PEP-8 coding style
2. Use type annotations (PEP-484) for all classes and functions.
3. Require docstrings for all classes & functions, large and small.
4. Maintain a minimum of 80% code coverage project wide (and aim for the same for each module).
5. Follow the DRY (don't repeat yourself) principle.  Instead of duplicating code, it should be shared whenever possible.

These are relatively common requirements across many python projects, so are likely familiar to most developers already.

In some specific circumstances we slightly deviate from PEP-8, such as minimum variable name requirements & on a case-by-case we may allow some code to deviate from formatting standards if it looks clearer / is easier to read with the deviation.

## Standards Enforcement ##

These standards are mostly reported by using `pylint`, with a configuration file setup to cause deviations from the standard result in linting errors.  Code coverage is reported via `pytest`'s `pytest-cov` module (`--cov` flag).

The standards are collectively enforced as we develop code, reinforced through our (PR)[PullRequests.md] procedure, and automated through our CI system (Github Actions) as part of the PR mergability requirements.
