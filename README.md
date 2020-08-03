<p align="center" >
   <img src="https://images.ctfassets.net/gm98wzqotmnx/3Ufcb7yYqcXBDlAhJ30gce/c237bb3254190795b30bf734f3cbc1d4/prefect-logo-full-gradient.svg" width="500" style="max-width: 500px;">
</p>

<p align="center">
   <a href=https://circleci.com/gh/PrefectHQ/prefect/tree/master>
      <img src="https://circleci.com/gh/PrefectHQ/server/tree/master.svg?style=shield&circle-token=28689a55edc3c373486aaa5f11a1af3e5fc53344">
   </a>

   <a href=https://github.com/ambv/black>
      <img src="https://img.shields.io/badge/code%20style-black-000000.svg">
   </a>

   <a href="https://join.slack.com/t/prefect-community/shared_invite/enQtODQ3MTA2MjI4OTgyLTliYjEyYzljNTc2OThlMDE4YmViYzk3NDU4Y2EzMWZiODM0NmU3NjM0NjIyNWY0MGIxOGQzODMxNDMxYWYyOTE">
      <img src="https://prefect-slackin.herokuapp.com/badge.svg">
   </a>
</p>

# Prefect Server

Please note: this repo is for Prefect Server development. If you want to run Prefect Server, install [Prefect](https://github.com/prefecthq/prefect) and run `prefect server start`.

## Overview

Prefect Server is an open-source backend

Prefect Server consists of a number of related services including:

- `postgres`: the database persistence layer
- `hasura`: a GraphQL API for Postgres (http://hasura.io)
- `graphql`: a Python-based GraphQL server that exposes mutations (actions) representing Prefect Server's logic
- `apollo`: an Apollo Server that serves as the main user interaction endpoint, and stitches together the `hasura` and `graphql` APIs.
- `towel`: a variety of utility services that provide maintenance routines, because a towel is just about the most massively useful thing an interstellar hitchhiker can carry.
  - `scheduler`: a service that searches for flows that need scheduling and creates new flow runs
  - `lazarus`: a service that detects when flow runs ended abnormally and should be restarted
  - `zombie_killer`: a service that detects when task runs ended abnormally and should be failed

These services are intended to be run within [Docker](https://www.docker.com/) and some CLI commands require [`docker-compose`](https://docs.docker.com/compose/) which helps orchestrate running multiple Docker containers simultaneously; if you don't already have Docker installed, [this link](https://download.docker.com/mac/stable/Docker.dmg) should allow you to download the latest stable release of Docker (including `docker-compose`) without having to create a Docker login.

## Installation

1. Don't Panic.

1. Make sure you have Python 3.7+ and Prefect installed:

   ```
   pip install prefect
   ```

1. Clone this repo, then install Prefect Server and its dependencies by running:

   ```
   pip install -e .
   npm install
   cd services/apollo && npm install
   ```

_Note: if installing for local development, it is important to install using the -e flag_

## Running the system

If you are doing local development on Prefect Server, it is best to run most services as local processes.
This allows for hot-reloading as code changes, setting debugging breakpoints, and generally speeds up the
pace of iteration.

In order to run the system:

1. Start the database and Hasura in Docker:

   ```bash
   prefect-server dev infrastructure
   ```

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
