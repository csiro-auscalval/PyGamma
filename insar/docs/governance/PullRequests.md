# Pull Request Process #

The `gamma_insar` project (requires all contributions)[ContributingCode.md] to go through a pull request process.  This is very similar to most pull requests developers would be familiar with working with other projects hosted in git repositories.

For completeness, we detail some specific recommendations and requirements in our PR process below.

## Code Review Guidelines ##

During the creation of the PR the contributor should make sure they appropriately describe the contents of the PR, and the purpose of the review / any areas of interest that may need focus (or that are large trivial areas and probably don't need attention), make sure they reference the relevant Github issues for that the PR is addressing, and requests a minimum of 2 reviewers for the review.

Once the review has started, the reviewers will provide comments on areas of they code they have questions/requests/etc about.
The contributor will address the comments and make appropriate modifications if they're needed.  Largely this process is a sanity check that all our quality standards are being followed, the new code/logic looks sane, tested properly, etc.

Whenever possible reviewers should try and focus on actual errors, design problems, quality concerns, etc.  Trying to keep nit-picking to a minimum reduces noise and makes the PR process clearer, although it's entirely up to developer discretion (some nit picks can be very useful / are worth it).

When changes are requested that could potentially be large or off-topic - it's recommended these be deferred to another issue if it's not a blocking issue for the PR and/or not related to the PR directly... this prevents PRs being strung along into longer living tasks, which ensures:
1. PRs don't live for weeks/months causing ongoing merge complications as other work is merged upstream.
2. The cognitive context people have about the PR's nuances don't get lost to time.
3. Mitigates the risk of PR contributors moving on while the PR is active.
4. Essentially removes the risks of feature/scope creep.

## Continuous Integration ##

Note: This section is hypothetical (we can't enable CI until the project is open source)

Our Github PR process is setup such that a PR does not become eligible to merge until all Github Actions have passed.  We have Github Actions for unit testing (with code coverage) and PyLint analysis.  This means developers *must* follow our coding standards & the code contribution guide to ensure their code is eligible for PR.

While we make an effort to ensure the CI system enforces all of our quality control and coding standards, we still encourage developers requesting a large PR to double check their work follows our standards as part of the review/PR process where possible.

## Approval ##

A pull request is only ready for merging only once there are a minimum of two approvals from two different reviewers.  This helps keep the quality of the project from degrading too much by ensuring multiple perspectives are taken into consideration, and that multiple sets of eyes have had a chance to find things that might not be obvious to everyone.

Additionally, the review can be considered complete once all comments that could be interpreted as needing some action taken are considered resolved (eg: the developer has addressed the concerns of all the unresolved comments).

Once these requirements are met, a PR can be considered approved and ready for merging.

## Merging ##

Before clicking the merge button, it's good practice to:
1. Double check everything has been covered properly in the code and review (especially for larger PRs)
2. Review the commit message and make any adjustments if the automatically generated one is missing any detail.

Once satisfied, click the merge button (we typically stick to squashed merges, but there's no limit on what kind of merge we accept - squashed merges just keep the history a bit cleaner/easier to read by associating each commit to a PR).
