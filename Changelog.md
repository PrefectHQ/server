# Changelog

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

