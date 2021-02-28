# JupyterLab Licenses

[![binder-badge]][binder]

[binder-badge]: https://mybinder.org/badge_logo.svg
[binder]:
  https://mybinder.org/v2/gh/bollwyvl/jupyterlab-meta/more-license-work?urlpath=lab/tree/README.md

> Work-in-progress repo for license reporting for JupyterLab 3.1.

## The Work

Work is proceeding on issues and PRs in two repos:

- `jupyterlab`
  - https://github.com/jupyterlab/jupyterlab/pull/9779
- `jupyterlab_server`
  - https://github.com/jupyterlab/jupyterlab_server/issues/160
  - https://github.com/jupyterlab/jupyterlab_server/pull/161

## The Problem

Historically, the pre-built JupyterLab shipped to `pypi` contained a large webpack build
of hundreds of first- and third-party libraries, without any sort of licenses
attribution.

With _federated modules_, every JupyterLab _extension_ constitutes a unique
distribution, which means this concern is shared by more parties.

## The Setup

[license-webpack-plugin](https://github.com/xz64/license-webpack-plugin) is the only
game in town for correctly capturing the licenses of all packages included in a build.
[Initial work](https://github.com/jupyterlab/jupyterlab/pull/9519) enabled this plugin,
but encountered a number of issues with _federated modules_. These have since been
fixed.

Further, the initial PR didn't actually _offer_ the licenses to the user.

In discussion with a number of parties, it became clear a number of tools are needed,
both at the CLI and in the web UI. Additionally, these license compliance tools will be
_uniquely_ interesting to downstream applications that remix JupyterLab core components,
and their upstreams.

## The Proposal

- offer a `/lab/api/licenses` API endpoint
- offer a `jupyter lab licenses` CLI
- offer a _Help &raquo; Licenses_ UI
