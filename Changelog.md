# Changelog

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

