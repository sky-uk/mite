# Contributing to the [Mite](https://github.com/sky-uk/mite) project

We greatly appreciate and encourage people contributing back into Mite.

## Coding Style

Mite code should adhere to the PEP8 standards for Python, with the following
exceptions that have been agreed upon by the core maintainers:

 * Line too long (Max: 100 chars) - E501
 * Line break before binary operator - W503
 * Lambda assignment - E731

## Quick Start

For instructions on getting dependencies installed and the unit tests run,
follow the instructions in the [DEV](https://github.com/sky-uk/mite/blob/master/DEV.md)
section of the documentation.

## Contributions

When contributing to Mite, you **must** adhere to the
following checklist.

These steps are in place to keep code and design quality to the highest
standard.

### Requirements

  * All exisiting unit tests have been run and they either:
    - [] All pass and no new additions are needed
    - [] They all pass and new passing tests have been created for new functionality
    - [] Some failed but this was expected and changes have been made to them to account for new features
  * [] Submission meets coding standards outlined [above](##coding-style)
  * [] Performance benchmarking has been run and observations included in the PR description
  * [] Additional documentation added where poignant 

## Core Maintainers

  * [Jordan Brennan](https://github.com/jb098) (Senior Performance Engineer - Sky Identity)
  * [Aaron Ecay](https://github.com/aecay) (Performance Engineer - Sky Identity)
  * [Davide Annunziata](https://github.com/DavAnnunz) (Performance Engineer - Sky Identity)
  * [Arron Canham](https://github.com/arroncanhamskyuk) (Performance Engineer - Sky Identity)

The Mite Maintainers Team are here to help facilitate the process of contributing
and offer guidance. If you have any questions or concerns please [talk to us via slack](https://sky.slack.com/messages/mite)
if you're a sky colleague or [via email](mailto:DL-Leeds-ID-PerformanceEngineering@sky.uk) for external contributers.

## Creating Issues

Submit issues to the issue tracker on the [appropriate
repository](https://github.com/sky-uk/mite) for suggestions,
recommendations, and bugs.

**Please note**: If it’s an issue that’s urgent / you feel you can fix yourself,
please feel free to make some changes and submit a [pull request](https://github.com/sky-uk/mite/pulls).
 We’d love to see your contributions.

## Git Workflow

With Mite being an open source project, we need to take greater care than
ever with our Git workflow and strategy. Please follow the below instructions
very closely.

**N.B.** If you fail to adhere to the agreed workflow, there is a risk that your
Pull Requests may not be accepted until any issues are rectified.

The Mite project operates under a feature branch worflow, which is hopefully
a pretty simple workflow to follow:

 * All features are developed on a sensibly named branch
   - Either a descriptive name
   - A link to an existing github issue
   - Or a JIRA ticket (internal)
 * When a feature is complete, it should be submitted back to master as pull request
 * All PRs will be reviwed by at least one core maintainer
 * Upon acceptance, all commits will be auto-squashed into a single commit

## Discussion

For discussion of issues and general project talk, head over to
[#mite](http://sky.slack.com/messages/mite) on Slack if you're a Sky colleague.

We still love to hear from you if you're an external contributer, the best way
to reach us for discussion is probably [via email](mailto:DL-Leeds-ID-PerformanceEngineering@sky.uk).

## Responsibilities

* All PRs must have at least one comment by a core maintainer within three working days.
* All additional comments must be replied to by a core maintainer with three working days

## Releases

* Release commits will be tagged by a core maintainer and will be available on [PyPi](link pending).
