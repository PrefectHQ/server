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

### Database passwords

A password for both db admin user and application user should be supplied. The former is needed to install pgcrypto.

Passwords can either be supplied via:

* `postgresql.global.existingSecret` or `postgresql.global.existingSecret` to specify existing secret.

* Specify both `postgresql.postgresqlPostgresPassword` for
admin, and `postgresql.postgresqlPassword` for application password.

### Ingresses

If ingresses for apollo and ui are enabled, at least one `hosts` entry
for each must be provided.

