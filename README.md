<p align="center" >
   <img src="https://images.ctfassets.net/gm98wzqotmnx/3Ufcb7yYqcXBDlAhJ30gce/c237bb3254190795b30bf734f3cbc1d4/prefect-logo-full-gradient.svg" width="500" style="max-width: 500px;">
</p>

<p align="center">
   <a href=https://circleci.com/gh/PrefectHQ/server/tree/master>
      <img src="https://circleci.com/gh/PrefectHQ/server/tree/master.svg?style=shield&circle-token=28689a55edc3c373486aaa5f11a1af3e5fc53344">
   </a>

   <a href=https://github.com/ambv/black>
      <img src="https://img.shields.io/badge/code%20style-black-000000.svg">
   </a>

   <a href="https://join.slack.com/t/prefect-community/shared_invite/enQtODQ3MTA2MjI4OTgyLTliYjEyYzljNTc2OThlMDE4YmViYzk3NDU4Y2EzMWZiODM0NmU3NjM0NjIyNWY0MGIxOGQzODMxNDMxYWYyOTE">
      <img src="https://prefect-slackin.herokuapp.com/badge.svg">
   </a>
</p>
<p align="center">
    <img src="https://images.ctfassets.net/gm98wzqotmnx/3mwImS57DEydMQXU1FCGG/6e36e2d49faf78cf4a166f123c2c43ca/image__5_.png" height="27">
</p>

**Please note**: If you are new to Prefect, we strongly recommend starting with [Prefect 2](https://docs.prefect.io/) and [Prefect Cloud 2](https://app.prefect.cloud), as they are in [General Availability](https://www.prefect.io/guide/blog/the-global-coordination-plane/). 

Prefect 1 Core, Server, and Cloud are our first-generation workflow and orchestration tools. You can continue to use them and we'll continue to support them while migrating users to Prefect 2. Prefect 2 can also be self-hosted and does not depend on this repository in any way.

If you're ready to start migrating your workflows to [Prefect 2](https://github.com/PrefectHQ/prefect), see our [migration guide](https://docs.prefect.io/migration-guide/).

# Prefect Server

Please note: this repo is for Prefect Server development. If you want to run Prefect Server, the best first step is to install [Prefect](https://github.com/prefecthq/prefect) and run `prefect server start`.

If you want to install Prefect Server on Kubernetes, take a look at the [Server Helm Chart](./helm/prefect-server).

If you would like to work on the Prefect UI or open a UI-specific issue, please visit [the Prefect UI repository](https://github.com/PrefectHQ/ui).

## Overview

[Prefect Server](https://docs.prefect.io/orchestration/server/overview.html) is an open source backend that makes it easy to monitor and execute your Prefect flows.

Prefect Server consists of a number of related services including:

- `postgres`: the database persistence layer
- `hasura`: a GraphQL API for Postgres (http://hasura.io)
- `graphql`: a Python-based GraphQL server that exposes mutations (actions) representing Prefect Server's logic
- `apollo`: an Apollo Server that serves as the main user interaction endpoint, and stitches together the `hasura` and `graphql` APIs
- `towel`: a variety of utility services that provide maintenance routines, because a towel is just about the most massively useful thing an interstellar hitchhiker can carry
  - `scheduler`: a service that searches for flows that need scheduling and creates new flow runs
  - `lazarus`: a service that detects when flow runs ended abnormally and should be restarted
  - `zombie_killer`: a service that detects when task runs ended abnormally and should be failed

These services are intended to be run within [Docker](https://www.docker.com/) and some CLI commands require [`docker-compose`](https://docs.docker.com/compose/) which helps orchestrate running multiple Docker containers simultaneously.

## Installation

1. Don't Panic.

1. Make sure you have Python 3.7+ and Prefect installed:

   ```
   pip install prefect
   ```

1. Clone this repo, then install Prefect Server and its dependencies by running:

   ```
   pip install -e .
   cd services/apollo && npm install
   ```

*Note: if installing for local development, it is important to install using the -e flag with `[dev]` extras: `pip install -e ".[dev]"`*

## Running the system as a developer

*Note: for [deploying Prefect Server](https://docs.prefect.io/orchestration/server/overview.html#deploying-prefect-server), please use the `prefect server start` CLI command in Prefect Core 0.13.0+.*

If you are doing local development on Prefect Server, it is best to run most services as local processes.
This allows for hot-reloading as code changes, setting debugging breakpoints, and generally speeds up the
pace of iteration.

In order to run the system:

1. Start the database and Hasura in Docker:

   ```bash
   prefect-server dev infrastructure
   ```

   _If when starting the infrastructure, you receive an error message stating_ `infrastructure_hasura_1 exited with code 137`, _it is likely a memory issue with Docker. Bumping Docker Memory to 8GB should solve this._

1. Run the database migrations and apply Hasura metadata:

   ```bash
   prefect-server database upgrade
   ```

1. In a new terminal, start the services locally:

   ```bash
   prefect-server dev services
   ```

You can use the `-i` (include) or `-e` (exclude) flags to choose specific services:

```bash
# run only apollo and graphql
prefect-server dev services -i apollo,graphql

# run all except graphql
prefect-server dev services -e graphql
```

## Running tests

Prefect Server has three types of tests:

- `unit tests`: used to validate individual functions
- `service tests`: used to verify functionality throughout Prefect Server
- `integration tests`: used to verify functionality between Prefect Core and Server

Prefect Server uses `pytest` for testing. Tests are organized in a way that generally mimics the `src` directory. For example, in order to run all unit tests
for the API and the GraphQL server, run:

```bash
pytest tests/api tests/graphql
```

Unit tests can be run with only `prefect-server dev infrastructure` running. Service and
integration tests require Prefect Server's services to be running as well.

## Filing an issue

Whether you'd like a feature or you're seeing a bug, we welcome users filing issues. Helpful
bug issues include:

- the circumstances surrounding the bug
- the desired behavior
- a minimum reproducible example

Helpful feature requests include:

- a description of the feature
- how the feature could be helpful
- if applicable, initial thoughts about feature implementation

**Please be aware** that Prefect Server feature requests that might compete with propriety [Prefect Cloud](https://cloud.prefect.io/) features will be rejected.

## License

Prefect Server is lovingly made by the team at [Prefect](https://www.prefect.io) and licensed under the [Prefect Community License](https://www.prefect.io/legal/prefect-community-license/). For information on how you can use, extend, and depend on Prefect Server to automate your data, take a look at our [license](https://github.com/PrefectHQ/server/blob/master/LICENSE) or [contact us](https://www.prefect.io/get-prefect#contact).
