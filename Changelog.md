# Changelog

## 2022.09.07 <Badge text="beta" type="success" />

Released on September 7, 2022.
### Helm

WARNING: This release of the Helm chart includes a breaking change with the upgrade from PostgreSQL 9 to 11. This is required because bitnami no longer hosts the old version of Postgres. If updating from a prior Helm chart release, please take care to back up your database.

- Allow users to specify a Kubernetes config map to be mounted as `jobTemplateFile` in the agent's container - [#379](https://github.com/PrefectHQ/server/pull/379)
- Improve init container template for graphql - [#370](https://github.com/PrefectHQ/server/pull/370)
- Create agent's env vars only if input variables are not empty - [#380](https://github.com/PrefectHQ/server/pull/380)
- Update PostgreSQL from ~9 to ~11 — [#375](https://github.com/PrefectHQ/server/pull/375)
- Allow specification of resources for the tenant creation job — [#371](https://github.com/PrefectHQ/server/pull/371)

### Contributors

- [Amit Zafran](https://github.com/amitza)
- [André Nogueira](https://github.com/aanogueira)
- [Michal Luščon](https://github.com/mluscon)
- [rcheatham-q](https://github.com/rcheatham-q)

## 2022.04.14 <Badge text="beta" type="success" />

Released on April 14, 2022.

### Fixes

- Fix issue where the Helm chart did not correctly set UI/Core image version tags - [#362](https://github.com/PrefectHQ/server/pull/362)

## 2022.03.29 <Badge text="beta" type="success" />

Released on March 29, 2022.

### Fixes

- Reduce maximum flow runs rescheduled by Lazarus at once - [#350](https://github.com/PrefectHQ/server/pull/350)

### Helm

- Add `includeChartNameInComponents` toggle to prefix component names with the chart name for improved UX as a subchart - [#355](https://github.com/PrefectHQ/server/pull/355)
- Fix missing server configs on towel deployment - [#346](https://github.com/PrefectHQ/server/pull/346)
### Contributors

- [Gabriel Gazola Milan](https://github.com/gabriel-milan)

## 2022.01.25 <Badge text="beta" type="success" />

Released on January 25, 2022.

### Enhancements

- Upgrade version of Hasura GraphQL engine to v2.1.1 - [#337](https://github.com/PrefectHQ/server/pull/337)

## 2022.01.12 <Badge text="beta" type="success" />

Released on January 12, 2022.

### Enhancements

- Upgrade Hasura to `v2.0.9` - [#328](https://github.com/PrefectHQ/server/pull/328)

### Helm

- Add `podAnnotations` - [#327](https://github.com/PrefectHQ/server/pull/327)
- Fix default `env` values - [#331](https://github.com/PrefectHQ/server/issues/331)
- Remove `PGPASSWORD` from towel service  - [#316](https://github.com/PrefectHQ/server/pull/316)

### Contributors

- [Lukáš Novotný](https://github.com/novotl)
- [Oreon Lothamer](https://github.com/oreonl)

## 2021.12.04 <Badge text="beta" type="success" />

Released on December 4, 2021.

### Enhancements

- Allow users to disable/enable apollo playground - [#326](https://github.com/PrefectHQ/server/pull/326)

### Contributors

- [Ahmed Ezzat](https://github.com/bitthebyte)

## 2021.11.30 <Badge text="beta" type="success" />

Released on November 30, 2021.

### Enhancements

- Allow configuration of the maximum artifact payload - [#320](https://github.com/PrefectHQ/server/pull/320)

### Helm

- Fix agent environment block construction - [#312](https://github.com/PrefectHQ/server/pull/312)
- Allow annotations to be provided for service accounts - [#314](https://github.com/PrefectHQ/server/pull/314)
- Allow custom flow run job template path to be provided to agents - [#322](https://github.com/PrefectHQ/server/pull/322)

### Contributors

- [Joël Luijmes](https://github.com/joelluijmes)
- [Rob Williams](https://github.com/rwilliams-exs)
- [Gabriel Gazola Milan](https://github.com/gabriel-milan)

## November 09, 2021 <Badge text="beta" type="success" />

Released on November 9, 2021.

### Fixes

- Preserves structural representation of serialized flows - [#306](https://github.com/PrefectHQ/server/pull/306)

### Security

- Upgrade `apollo-server` to address GraphQL playground vulnerability. See [the advisory](https://github.com/apollographql/apollo-server/security/advisories/GHSA-qm7x-rc44-rrqw) for details.

## October 21, 2021 <Badge text="beta" type="success" />

Released on October 21, 2021.

### Features

- Add ability to set keep alive timeout for graphql server - [#290](https://github.com/PrefectHQ/server/pull/290)
- Add handling a keepalive value to Apollo via env variable APOLLO_KEEPALIVE_TIMEOUT - [#293](https://github.com/PrefectHQ/server/pull/293)

### Enhancements

- Add a submitted state lock to prevent the same flow from being run by multiple agents - [#291](https://github.com/PrefectHQ/server/pull/291)
- Add default flow parameters to flow runs to have consistent flow run parameter history - [#298](https://github.com/PrefectHQ/server/pull/298)

### Fixes

- Fix setting `imagePullSecrets` in k8s jobs with Prefect flows in Prefect Server Helm chart - [#289](https://github.com/PrefectHQ/server/pull/289)

### Contributors

- [Joe M.](https://github.com/joe1981al)
- [Joe McDonald](https://github.com/joe1981al)

## Sep 2, 2021 <Badge text="beta" type="success" />

Released on September 2, 2021.

### Enhancements

- Make maximum number of scheduled runs per flow configurable - [#280](https://github.com/PrefectHQ/server/issues/280)
- Increase Apollo payload size limit to 5mb - [#273](https://github.com/PrefectHQ/server/pull/273)
- Separate out task and edge registration to better handle large flow registrations - [#277](https://github.com/PrefectHQ/server/pull/277)

### Fixes

- Update Helm chart RoleBinding API version - [#276](https://github.com/PrefectHQ/server/pull/276)

### Contributors

- [Bouke Krom](https://github.com/bouke-sf)
- [Guy Maliar](https://github.com/gmaliar)

## July 06, 2021 <Badge text="beta" type="success" />

Released on July 6, 2021.

### Enhancements

- Add traceback info to some unexpected logs for debugging - [#259](https://github.com/PrefectHQ/server/pull/259)
- Add the option to defer setting a flow run state to scheduled when creating a FlowRun - [#261](https://github.com/PrefectHQ/server/pull/261)

## May 25, 2021 <Badge text="beta" type="success" />

Released on May 25, 2021.

### Enhancements

- Introduce **kwargs to `create_logs` for Cloud compatibility - [#247](https://github.com/PrefectHQ/server/pull/247)

## April 27, 2021 <Badge text="beta" type="success" />

Released on April 27, 2021.

### Enhancements

- Simplify `LoopService.loop_seconds` handling and add debug mode to speedup tests - [#242](https://github.com/PrefectHQ/server/pull/242)

### Database Migrations

- Add unique constraint for flow run idempotency - [#219](https://github.com/PrefectHQ/server/pull/219)

## April 6, 2021 <Badge text="beta" type="success" />

Released on April 6, 2021.

### Features

- Helm: Add ingress support for `ui` and `apollo` components - [#229](https://github.com/PrefectHQ/server/pull/229)

### Enhancements

- Add delete_flow_group mutation - [#228](https://github.com/PrefectHQ/server/pull/228)
- Batch task and edge insertion during flow creation - [#238](https://github.com/PrefectHQ/server/pull/238)

### Fixes

- Log `set_schedule_active` failure while creating a flow - [#236](https://github.com/PrefectHQ/server/pull/236)

### Contributors

- [Augustinas Šimelionis](https://github.com/aaugustinas)

## March 20, 2021 <Badge text="beta" type="success" />

Released on March 20, 2021.

### Enhancements

- Add more permissions to agent role in helm chart - [#221](https://github.com/PrefectHQ/server/pull/221)
- Set uvicorn server log level and access logs - [#217](https://github.com/PrefectHQ/server/pull/217)

### Fixes

- Ensure the scheduler queries with deterministic order - [#215](https://github.com/PrefectHQ/server/pull/215)
- Ensure that errors in scheduling do not interrupt other scheduling operations - [#224](https://github.com/PrefectHQ/server/pull/224)

### Database Migrations

- Improve run detail triggers when version is the same or missing - [#218](https://github.com/PrefectHQ/server/pull/218)

### Contributors

- [Peter Roelants](https://github.com/peterroelants)

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
