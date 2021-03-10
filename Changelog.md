# Changelog

## March 10, 2021 <Badge text="beta" type="success" />

Released on March 10, 2021.

### Features

- Release the Server Helm Chart to a Helm repository - [#209](https://github.com/PrefectHQ/server/pull/209)

## March 6, 2021 <Badge text="beta" type="success" />

Released on March 6, 2021.

### Enhancements

- Add `APIError` to replace 'database query error' and consolidate Cloud/Server exception types - [#204](https://github.com/PrefectHQ/server/pull/204)
- Improve `archive_flow` performance with auto-scheduled flow runs - [#206](https://github.com/PrefectHQ/server/pull/206)

### Fixes

- Allow `create_agent` to be called without passing settings - [#207](https://github.com/PrefectHQ/server/pull/207)

## March 4, 2021 <Badge text="beta" type="success" />

Released on March 4, 2021.

### Enhancements

- Upgrade hasura version to 1.3.3 - [#188](https://github.com/PrefectHQ/server/pull/188)
- Upgrade apollo base image to debian-buster - [#198](https://github.com/PrefectHQ/server/pull/198)
- Install `tini` from apt instead of GitHub in apollo image - [#199](https://github.com/PrefectHQ/server/pull/199)

### Fixes

- Fixed the execution of the `create-tenant-job` in the Helm charts to allow for custom Apollo ports - [#201](https://github.com/PrefectHQ/server/pull/201)
- Improve `delete_flow_run` performance by avoiding slow deletion triggers - [#202](https://github.com/PrefectHQ/server/pull/202)

### Breaking Changes

- Server instances with managed databases require [manual SQL to upgrade](https://github.com/PrefectHQ/server/tree/master/helm/prefect-server#Upgrading-Hasura) - [#188](https://github.com/PrefectHQ/server/pull/188)

### Contributors

- [Jay Vercellone](https://github.com/jverce)

## February 22, 2021 <Badge text="beta" type="success" />

Released on February 22, 2021.

### Fixes

- Add `tini` init process to GraphQL and Apollo containers to reap zombies - [#191](https://github.com/PrefectHQ/server/pull/191)

## February 18, 2021 <Badge text="beta" type="success" />

Released on February 18, 2021.

### Enhancements

- Capture all 'connect' errors and uniformize into DB query errors - [#189](https://github.com/PrefectHQ/server/pull/189)

## February 12, 2021 <Badge text="beta" type="success" />

Released on February 12, 2021.

### Features

- Helm: Optionally create the default tenant before running Agent - [#183](https://github.com/PrefectHQ/server/pull/183)

### Enhancements

- Cancel ad-hoc created flow runs instead of deleting them when archiving a flow - [#185](https://github.com/PrefectHQ/server/pull/185)
- Upgrade pydantic to 1.7.x - [#187](https://github.com/PrefectHQ/server/pull/187)

### Fixes

- Fix asyncpg errors on Apple M1 / arm64 - [#186](https://github.com/PrefectHQ/server/pull/186)

### Contributors

- [Michał @ DataRevenue](https://github.com/michcio1234)

## February 5, 2021 <Badge text="beta" type="success" />

Released on February 5, 2021.

### Enhancements

- Install curl in server docker image for healthchecks - [#182](https://github.com/PrefectHQ/server/pull/182)
- Improve `LoopService` interval handling - [#43](https://github.com/PrefectHQ/server/pull/43)

### Breaking Changes

- Move to `YYYY.MM.DD` versioning scheme away from `YYYY-MM-DD` - [#178](https://github.com/PrefectHQ/server/pull/178)

## January 25, 2021 <Badge text="beta" type="success" />

Released on January 25, 2021.

### Enhancements

- Add 'description' field for Flow Groups along with routes for updating - [#177](https://github.com/PrefectHQ/server/pull/177)

## January 19, 2021 <Badge text="beta" type="success" />

Released on January 19, 2021.

### Enhancements

- Add `sum` aggregate to ORM  - [#174](https://github.com/PrefectHQ/server/pull/174)

## January 5, 2021 <Badge text="beta" type="success" />

Released on January 5, 2021.

### Features

- Support per-flow-run and per-flow-group `run_config` overrides - [#166](https://github.com/PrefectHQ/server/pull/166)

### Enhancements

- Upgrade Apollo NodeJS to `14.15.1` - [#153](https://github.com/PrefectHQ/server/pull/153)
- Helm: configure strategy for deployment - [#165](https://github.com/PrefectHQ/server/pull/165)
- Allow for timezone specification on flow group schedules - [#169](https://github.com/PrefectHQ/server/pull/169)

### Database Migrations

- Add `flow_group.run_config` and `flow_run.run_config` - [#166](https://github.com/PrefectHQ/server/pull/166)

### Contributors

- [Joël Luijmes](https://github.com/joelluijmes)

## December 16, 2020 <Badge text="beta" type="success" />

Released on December 16, 2020.

### Enhancements

- Add the `events` RBAC permission to agents created by the helm chart - [#157](https://github.com/PrefectHQ/cloud/pull/157)

## December 14, 2020 <Badge text="beta" type="success" />

Released on December 14, 2020.

### Enhancements

- Add documentation on how to connect the CLI to a remote deployed server - [#159](https://github.com/PrefectHQ/server/pull/159)
- Refactor the Zombie Killer to rely entirely on flow run heartbeats - [#158](https://github.com/PrefectHQ/server/pull/158)
- Add support for custom Hasura root fields - [#161](https://github.com/PrefectHQ/server/pull/161)

### Fixes

- Add jobs/status to role for agent - [#154](https://github.com/PrefectHQ/server/pull/154)

### Contributors

- [Joël Luijmes](https://github.com/joelluijmes)
- [Pedro Martins](https://github.com/pedrocwb)

## December 4, 2020 <Badge text="beta" type="success" />

Released on December 4, 2020.

### Enhancements

- Add flag for shutting down loop services - [#144](https://github.com/PrefectHQ/server/pull/144)
- Support configurable primary keys in ORM - [#145](https://github.com/PrefectHQ/server/pull/145)
- Add support for expanded Hasura update operations - [#146](https://github.com/PrefectHQ/server/pull/146)
- Helm chart: Always pull prefecthq docker images by default - [#151](https://github.com/PrefectHQ/server/pull/151)

### Fixes

- Listen on all agent interfaces for healthchecks - [#148](https://github.com/PrefectHQ/server/pull/148)

### Database Migrations

- Add task run name index for text search - [#149](https://github.com/PrefectHQ/server/pull/149)

### Contributors

- [Vladimir Zoubritsky](https://github.com/vogre)

## November 29, 2020 <Badge text="beta" type="success" />

Released on November 29, 2020.

### Enhancements

- Add KubernetesAgent to the Helm chart - [#136](https://github.com/PrefectHQ/server/pull/136)
- Add two new GraphQL routes for Core functionality - [#143](https://github.com/PrefectHQ/server/pull/143)

### Fixes

- Fix handling for managed postgres usernames with `@` signs - [#139](https://github.com/PrefectHQ/server/pull/139)

## November 13, 2020 <Badge text="beta" type="success" />

Released on November 13, 2020.

### Enhancements

- Add the Prefect Core version to the api query - [#126](https://github.com/PrefectHQ/server/pull/126)
- Remove global 24 hour expiration on flow run idempotency keys - [#134](https://github.com/PrefectHQ/server/pull/134)

### Fixes

- prefect-server dev infrastructure would sometimes fail to start with 'connection closed' - [#130](https://github.com/PrefectHQ/server/pull/130)
- Fix helm chart when using existing postgres instance - [#132](https://github.com/PrefectHQ/server/pull/132)
- Fix scheduling duplicate runs due to expired idempotency keys - [#134](https://github.com/PrefectHQ/server/pull/134)

### Contributors

- [Joël Luijmes](https://github.com/joelluijmes)

## November 11, 2020 <Badge text="beta" type="success" />

Released on November 11, 2020.

### Features

- Add experimental Helm chart for deploying in K8s - [#123](https://github.com/PrefectHQ/server/pull/123)

### Contributors

- [Jonas Bernhard](https://github.com/yolibernal)
- [Joël Luijmes](https://github.com/joelluijmes)
- [Shaun Cutts](https://github.com/shaunc)

## November 10, 2020 <Badge text="beta" type="success" />

Released on November 10, 2020.

### Features

- Add API for persisting and retrieving task run artifacts - [#121](https://github.com/PrefectHQ/server/pull/121)

## October 29, 2020 <Badge text="beta" type="success" />

Released on October 29, 2020.

### Features

- Add idempotency keys to `flows.create_flow` - [#116](https://github.com/PrefectHQ/server/pull/116)

### Fixes

- Expose database upgrade errors during infrastructure start  - [#117](https://github.com/PrefectHQ/server/pull/117)

## October 27, 2020 <Badge text="beta" type="success" />

Released on October 27, 2020.

### Fixes

- Check for existence of agent before updating flow run agent - [#114](https://github.com/PrefectHQ/server/issues/114)

## October 22, 2020 <Badge text="beta" type="success" />

Released on October 22, 2020.

### Enhancements

- Update flow settings graphql logic to use supported API routes - [#113](https://github.com/PrefectHQ/server/pull/113)

## October 14, 2020 <Badge text="beta" type="success" />

Released on October 14, 2020.

### Fixes

- Allow for scheduling different parameters and different run labels at the exact same time - [#111](https://github.com/PrefectHQ/server/pull/111)

## October 13, 2020 <Badge text="beta" type="success" />

Released on October 13, 2020.

### Features

- Allow for scheduling changing labels on a per-flow run basis - [#109](https://github.com/PrefectHQ/server/pull/109)

### Fixes

- Fixes issue with Agent Config schema - [#107](https://github.com/PrefectHQ/server/pull/107)

## September 24, 2020 <Badge text="beta" type="success" />

Released on September 24, 2020.

### Enhancements

- Registering agents will now retrieve IDs from matching entries in order to prevent duplication - [#95](https://github.com/PrefectHQ/server/pull/95)
- Add routes for setting run names - [#77](https://github.com/PrefectHQ/server/pull/77)

### Fixes

- Fix `name` field in `delete_agent` GraphQL resolver - [#95](https://github.com/PrefectHQ/server/pull/95)
- Replace all uses of `database.models` with `prefect.models` - [#94](https://github.com/PrefectHQ/server/pull/94)

### Database Migrations

- Add task run name - [#77](https://github.com/PrefectHQ/server/pull/77)
- Add index on `flow_run.agent_id` - [#93](https://github.com/PrefectHQ/server/pull/93)

## September 15, 2020 <Badge text="beta" type="success" />

Released on September 15, 2020.

### Enhancements

- Hasura metadata archives use the most recent alembic revision ID - [#78](https://github.com/PrefectHQ/server/pull/78)

### Fixes

- Fix and consolidate behavior for active schedules - [#86](https://github.com/PrefectHQ/server/issues/86)

## September 11, 2020 <Badge text="beta" type="success" />

Released on September 11, 2020.

### Features

- Add database structure and routes for persisting Agents - [#58](https://github.com/PrefectHQ/server/pull/58)

### Enhancements

- Add route for querying mapped children - [#73](https://github.com/PrefectHQ/server/pull/73)

### Fixes

- Fix __init__.py for deprecated API module - [#71](https://github.com/PrefectHQ/server/pull/71)

### Breaking Changes

- Remove `run_count` and `duration` columns - [#72](https://github.com/PrefectHQ/server/pull/72)

### Database Migrations

- Increase performance of state update triggers - [#72](https://github.com/PrefectHQ/server/pull/72)

## September 1, 2020 <Badge text="beta" type="success" />

Released on September 1, 2020.

### Enhancements

- Automatically upgrade local database - [#69](https://github.com/PrefectHQ/server/pull/69)

### Fixes

- Fix flow run creation not using default parameters from flow group - [#64](https://github.com/PrefectHQ/server/issues/64)
- Ensure Lazarus ignores flow runs with active tasks - [#67](https://github.com/PrefectHQ/server/pull/67)

### Deprecations

- Deprecate flow settings that are actually flow group settings - [#63](https://github.com/PrefectHQ/server/pull/63)

## August 26, 2020 <Badge text="beta" type="success" />

Released on August 26, 2020.

### Enhancements

- Refactor Lazarus and Zombie Killer for modularity - [#46](https://github.com/PrefectHQ/server/pull/46)
- Add API mode to queryable reference info - [#59](https://github.com/PrefectHQ/server/pull/59)

## August 21, 2020 <Badge text="beta" type="success" />

Released on August 21, 2020.

### Enhancements

- Upgrade Hasura to 1.3.0 - [#18](https://github.com/PrefectHQ/server/pull/18)
- Set schedule to inactive if neither Flow nor Flow Group have a schedule - [#37](https://github.com/PrefectHQ/server/pull/37)
- Dedupe flow group labels when set - [#40](https://github.com/PrefectHQ/server/pull/40)
- Set Apollo's `post-start.sh` script to wait for the GraphQL service's healthcheck - [#41](https://github.com/PrefectHQ/server/pull/41)
- Upgrade Hasura to 1.3.1 - [#52](https://github.com/PrefectHQ/server/pull/52)
- Use Hasura default cache size - [#52](https://github.com/PrefectHQ/server/pull/52)
- Adds RELEASE_TIMESTAMP for UI to display - [#54](https://github.com/PrefectHQ/server/pull/54)

### Breaking Changes

- Remove unused UI from services CLI - [#45](https://github.com/PrefectHQ/server/pull/45)
- Cloud hooks require explicit states - [#51](https://github.com/PrefectHQ/server/pull/51)
- Cloud hooks do not match state parents - [#51](https://github.com/PrefectHQ/server/pull/51)
- Remove unused code and config settings - [#53](https://github.com/PrefectHQ/server/pull/53)

### Database Migrations

- Remove unused `state_id` column - [#35](https://github.com/PrefectHQ/server/pull/35)

## 0.1.0

### Features

- Release

### Enhancements

- None

### Infrastructure

- None

### Fixes

- Fixes bug where updating a Flow Group schedule didn't clear old scheduled runs - [#9](https://github.com/PrefectHQ/server/pull/9)

### Breaking Changes

- None

### Deprecations

- None

