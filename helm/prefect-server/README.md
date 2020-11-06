# Prefect Server Helm Chart

## Usage

1. Clone repository
2. From this directory:

```
$ helm install <name-to-label-release> . [helm options]
```

## Options:

See comments in `values.yaml`.

### Database

The database can be deployed by this chart or be provided externally. 
We strongly recommend that you do not deploy a production database using this chart, the provided database is primarily for testing purposes.

An external database will require some minimal setup for Hasura.
The following needs to be run or the user should have permissions to execute it and Hasura will run it on startup:
```sql
      CREATE EXTENSION IF NOT EXISTS pgcrypto;
      CREATE EXTENSION IF NOT EXISTS "pg_trgm";
      SET TIME ZONE 'UTC';
```

### Ingresses

If ingresses for apollo and ui are enabled, at least one `hosts` entry
for each must be provided.

