# Contributing Code #

Code contributions to `gamma_insar` are greatly appreciated!  To contribute code to the project developers will need to follow our coding standards and quality requirements detailed in this document.

Code contributions are accepted from branches of the `pygamma_workflow` branch from our (Github repo)[https://github.com/GeoscienceAustralia/gamma_insar], once developers have code changes they want to submit to the project they can follow the pull request guide (here)[PullRequests.md].

For developers unfamiliar with the pull-request model, Github provides (guides and tutorials)[https://docs.github.com/en/get-started] for getting started.

## Github Issue ##

Before any work is done, it's good practice to have a (Github issue)[https://github.com/GeoscienceAustralia/gamma_insar/issues] for the project.
Doing this lets other people know what work people are interested in having done on the project, let's other developers give feedback and advice on the issue, helps prevent people duplicating effort by working on the same thing without realising it, and provides a place to let people know how you're progressing or what problems you might be encountering.

Whenever possible, it's reasonable to want to group closely related *small* chunks of work together in a single issue.  If an issue you're having or some work you're wanting to contribute matches an existing issue, and isn't too far out of scope - it's recommended to try and add your work to existing issues if they're available.

This is standard practice for all work being done on `gamma_insar` by the project's developers, and highly encouraged for third-party contributors to help everyone have the smoothest development experience possible.

Raising an issue is also a good way to get others interested and potentially help you implement your changes!

## Coding Style ##

We try and keep all code in the `gamma_insar` project consistent by keeping to a single coding style & design paradigms across all the modules.

The coding standards are documented in more detail [in another document](CodingStandards.md)

Deviations from the standard are likely to be raised in PRs for any contributions made, so sticking to the standard will prevent future work having to clean things up during PR.  Deviations are also likely to by raised during the linting process described below.

## PyLint ##

To help with complying with code style & keep the code base from regressing, we enforce PyLint errors as CI errors. PyLint metrics are a big part of contributing code to `gamma_insar` as contributions will not pass PR if CI doesn't pass, and CI won't pass if there are PyLint errors.

All contributions accepted by PR will need to ensure they don't add any extra PyLint errors, otherwise they won't pass CI or be able to be merged.

## Unit Testing & Code Coverage ##

We try and ensure at least 80% of all code in `gamma_insar` is covered by unit tests, and strive to exceed that when ever possible.  Much like linting, unit tests are also part of our CI setup and will also prevent a PR from being accepted tests fail with the code contribution applied and/or if code coverage falls below 80% as a result of the code contributions.

We really appreciate everyone ensuring new code they add is properly tested with unit tests that genuinely test the *outcomes* of their new code when run against **both** valid *and* invalid data (code coverage of error/failure code paths is just as important as the normal code path).

## Pull Requests ##

Once you're happy with your modifications and are ready to get it merged upstream into the official repo, it's time to start the (pull request process)[PullRequests.md].

All contributions are required to go through PR with a minimum of 2 reviewers and 2 approvals, as well as pass all CI checks (eg: unit testing and linting) before it can be merged up-stream.

Once your PR has been accepted, congratulations!  At this point you should be able to update any relevant information in the appropriate github issues and close them if appropriate.
