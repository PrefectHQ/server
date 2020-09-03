# Prefect server helm chart

Very experimental version of helm chart to deploy Prefect server.

## Installation

1. Clone repository
2. From this directory:

```
$ helm install --namespace <namespace> <name> ./prefect-server [helm options]
```
Where `<namespace>` is namespace to install into, and `<name>` is name
of instance.

## Options:

See comments in `values.yaml`.

### Database & database passwords

The database can be either external or internal (via `postgresqlEnabled`, default internal). 
If it is external, the following db  setup must either already be done, or the application 
database user should have necessary permissions to execute it (as it is in the hasura init 
container startup script):
```sql
      -- create pgcrypto extension, required for UUID
      CREATE EXTENSION IF NOT EXISTS pgcrypto;
      CREATE EXTENSION IF NOT EXISTS "pg_trgm";
      SET TIME ZONE 'UTC';
```

For internal use, this is executed on database creation by the `postgres` user. Because of this, 
a password for both the postgres user and the application user should be supplied.

Passwords can either be supplied either via an existing secret in the form required by [bitnami/postgresql](https://hub.helm.sh/charts/bitnami/postgresql), or via explicitly specified secrets:

* `postgresql.global.existingSecret` or `postgresql.global.existingSecret` to specify existing secret.

* Specify both `postgresql.postgresqlPostgresPassword` for
admin, and `postgresql.postgresqlPassword` for application password.

By default, the internal database creates a PVC for 8Gi storage.

### Ingresses

If ingresses for apollo and ui are enabled, at least one `hosts` entry
for each must be provided.

