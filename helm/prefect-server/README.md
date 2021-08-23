# Prefect Server Helm Chart

<!-- TOC -->

- [Usage](#usage)
    - [Installing released versions](#installing-released-versions)
        - [Verifying package integrity](#verifying-package-integrity)
    - [Installing development versions](#installing-development-versions)
    - [Upgrading](#upgrading)
        - [Important notes about upgrading](#important-notes-about-upgrading)
- [Options:](#options)
    - [Tenant](#tenant)
    - [KubernetesAgent](#kubernetesagent)
    - [Database](#database)
    - [Ingress](#ingress)
- [Versioning](#versioning)
    - [Development](#development)
- [Connecting to your Server](#connecting-to-your-server)
    - [Configure `prefect` to point to your service](#configure-prefect-to-point-to-your-service)
    - [Forward your service to localhost](#forward-your-service-to-localhost)
- [Troubleshooting](#troubleshooting)
    - [The UI loads but the dashboard is blank](#the-ui-loads-but-the-dashboard-is-blank)
    - [The UI loads but cannot connect to the API](#the-ui-loads-but-cannot-connect-to-the-api)
    - [The database deploys correctly but other services fail with "bad password"](#the-database-deploys-correctly-but-other-services-fail-with-bad-password)
    - [The agent is running but when I look at the logs I am getting GraphQL errors](#the-agent-is-running-but-when-i-look-at-the-logs-i-am-getting-graphql-errors)
    - [Upgrading Hasura](#upgrading-hasura)

<!-- /TOC -->

## Usage

### Installing released versions

The Helm chart is automatically versioned and released alongside Server.
For each Github Release of Server there is a corresponding version of the Helm chart.
The charts are hosted in a [Helm repository](https://helm.sh/docs/chart_repository/) deployed to the web courtesy of Github Pages.

1. Let you local Helm manager know about the repository.

    ```
    $ helm repo add prefecthq https://prefecthq.github.io/server/
    ```

2. Sync versions available in the repo to your local cache.

    ```
    $ helm repo update
    ```

3. Search for available charts and versions

    ```
    $ helm search repo [name]
    ```

4. Install the Helm chart

    Using default options
    ```
    $ helm install prefecthq/prefect-server --generate-name
    ```

    Setting some typical flags for customization
    ```shell
    # The kubernetes namespace to install into, can be anything or excluded to install in the default namespace
    NAMESPACE=prefect-server
    # The Helm "release" name, can be anything but we recommend matching the chart name
    NAME=prefect-server
    # The path to your config that overrides values in `values.yaml`
    CONFIG_PATH=path/to/your/config.yaml
    # The chart version to install
    VERSION=2021.03.06

    helm install \
        --namespace $NAMESPACE \
        --version $VERSION \
        --values $CONFIG_PATH \
        $NAME \
        prefecthq/prefect-server
    ```

    _If chart installation fails, `--debug` can provide more information_

    See [Helm install docs](https://helm.sh/docs/helm/helm_install/) for all options.

#### Verifying package integrity

_Checking package integrity is not required and is included as an optional security measure_

The hosted charts are signed using GPG to ensure package integrity.

1. Import the public key used to sign the packages
    ```
    $ echo "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" \
        | base64 --decode \
        | gpg --import
    ```

2. If using GPG newer than v2, you may need to create a "legacy" `.pub` file to satisfy Helm
    _This will override an existing file, do not run if this file exists_
    ```
    $ gpg --export > ~/.gnupg/pubring.gpg
    ```

3. Add `--verify` to your installation and upgrade commands to verify package integrity

### Installing development versions

Development versions of the Helm chart will always be available directly from this Github repository.

1. Clone repository

2. Change to this directory

3. Download the postgresql dependency if you are not using an existing database

    ```
    $ helm dependency update
    ```

4. Install the chart

    ```
    $ helm install . --generate-name
    ```

### Upgrading

1. Look up the name of the last release

    ```
    $ helm list
    ```

2. Run the upgrade

    ```shell
    # Set this name to the name of your last Helm release
    NAME=prefect-server
    # Choose a version to upgrade to or omit the flag to use the latest version
    VERSION=2021.03.06

    helm upgrade $NAME prefecthq/prefect-server --version $VERSION
    ```

    For development versions, make sure your cloned repository is updated (`git pull`) and reference the local chart
    ```
    $ helm upgrade $NAME .
    ```

3. Upgrades can also be used enable features or change options

    ```shell
    NAME=prefect-server

    helm upgrade \
        $NAME \
        prefecthq/prefect-server \
        --set agent.enabled=true \
        --set jobs.createTenant.enabled=true
    ```

#### Important notes about upgrading

- Updates will only update infrastructure that is modified.
- You will need to continue to set any values that you set during the original install (e.g. `--set agent.enabled=true` or `--values path/to/config.yaml`).
- If you are using the postgresql subchart with an autogenerated password, it will complain that you have not provided that password for the upgrade.
  Export the password as the error asks then set it within the subchart using
    ```
    $ helm upgrade ... --set postgresql.postgresqlPassword=$POSTGRESQL_PASSWORD
    ```

## Options:

See comments in `values.yaml`.

### Tenant

A tenant is needed for the server API to be operational.
If there is no tenant in the database, the UI dashboard will fail to display and agents will error.

To automatically create a default tenant, use the flag `--set jobs.createTenant.enabled=true`.

To create the tenant manually when your chart is already installed,
run `prefect backend server && prefect server create-tenant --name default --slug default` to create a default tenant.
Check out [Connecting to your Server](#connecting-to-your-server) to connect your local `prefect` to your server before creating the tenant.

### KubernetesAgent

A [Prefect KubernetesAgent](https://docs.prefect.io/orchestration/agents/kubernetes.html) that queries for flows and runs them on your cluster can be installed but is not included by default.
Add the flag `--set agent.enabled=true` to the `helm install` command to include the agent.

### Database

The database can be deployed by this chart or be provided externally.
We strongly recommend that you do not deploy a production database using this chart, the provided database is primarily for testing purposes.
The provided database will **not** persist your data by default.
When connecting to an external database, PostgreSQL 11+ is recommended.

An external database will require some minimal setup for Hasura.
The following needs to be run or the user should have permissions to execute it and Hasura will run it on startup:

```sql
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
SET TIME ZONE 'UTC';
```

### Ingress

Ingress rule creation is suported for `ui` and `apollo` components of this chart. You must have an Ingress controller (i.e. nginx) installed to your cluster and configured independently of this chart.

To create an Ingress rule for a component,
1. Disable direct service access by setting `<component>.service.type` to `ClusterIP` instead of `LoadBalancer`
2. Enable the Ingress by setting `<component>.ingress.enabled` to `true`
3. Configuring the list of hosts at `<component>.ingress.hosts` to include your domains. _There is an example in values.yaml_ 

Created component Ingress rules will be automatically configured to forward traffic from specified hosts to coresponding services.

You can secure an Ingress by specifying a `Secret` that contains a TLS private key and certificate. For information how to setup the secret, refer to the [Ingress section of the official Kubernetes documentation](https://kubernetes.io/docs/concepts/services-networking/ingress/#tls).

## Versioning

Released Helm charts have versions matching Prefect Server image tags.
The chart uses `appVersion` to infer the image tags to download.
The `appVersion` will always match the `version` of an official release.

If you need to override the version of the Server image tags, you may do so globally with `--set serverVersionTag=<VERSION>` or override each service individually.

Some services rely on related Prefect images. 
These are set using `prefectVersionTag` and `uiVersionTag` which is pinned to the latest releases on chart release.
You may want to manage these version tags separately as Prefect Core and the UI are released more frequently than the Server.

If using the agent in production, we recommend ensuring `prefectVersionTag` matches the version of Prefect you are using to ensure the agent matches your flow.

### Development

The Helm chart in this repo sets the `appVersion` to `latest` to always pull the most recent images.
The chart `version` _must_ follow semantic versioning per Helm's standards and is pinned to `0.0.0`.

The default `imagePullPolicy` is `Always` so images will be updated when your deployments are rolled over.
This could result in some deployments being on mismatched versions which may not be guaranteed to work well together.

## Connecting to your Server

When you run `prefect backend server`, it configures the CLI to expect Server interactions rather than Prefect Cloud. By default, the CLI looks for the Server API at `localhost`. To connect the CLI to your newly deployed server, you'll either need to point the CLI to an external IP or forward the service to `localhost`

### Configure `prefect` to point to your service

To designate your local `prefect` to point to the Kubernetes server,
you can change the host in the user configuration file `~/.prefect/config.toml`.

```
[server]
  host = "http://<EXTERNAL-IP>"
```
Run `kubectl get services --namespace <namespace>` to obtain the Apollo API external ip address.
To review the configuration file run `prefect config`.

### Forward your service to localhost

Alternatively, you can port-forward the apollo service to your localhost
`kubectl port-forward svc/<APOLO-SERVICE> 4200:4200 -n <namespace>`.

## Troubleshooting

### The UI loads but the dashboard is blank

If you go to the 'Home' page, it will likely direct you to create a tenant. Without a tenant, the dashboard cannot display.

See the [Tenant](#tenant) section to learn how to create a default tenant.

### The UI loads but cannot connect to the API

Check that the API url is correct under the `server_url` key at the UI url `/settings.json` e.g. `http://localhost:8080/settings.json`.
This should match the url that the Apollo service is deployed to e.g. `http://localhost:4200/graphql`
This endpoint must be accessible by *the user* of the UI, not just the server, since requests come from the user's browser.

### The database deploys correctly but other services fail with "bad password"

If you are using the subchart deployed database with persistence enabled,
it is likely the password for the user has persisted between deployments in the PVC for the database but the secret has been regenerated by the Helm chart and does not match.
Deploy and set the 'postgresql.existingSecret' option or set a constant password at `postgresql.postgresqlPassword`.

### The agent is running but when I look at the logs I am getting GraphQL errors

The following error is typically caused by the lack of a tenant. Create a default tenant and the agent will restart automatically.
```
[2020-11-13 19:16:02,083] ERROR - agent | 400 Client Error: Bad Request for url: http://my-release-apollo.default:4200/graphql

This is likely caused by a poorly formatted GraphQL query or mutation. GraphQL sent:

query {
    mutation($input: get_runs_in_queue_input!) {
            get_runs_in_queue(input: $input) {
                flow_run_ids
        }
    }
}
variables {
    {"input": {"before": "2020-11-13T19:16:01.973734+00:00", "labels": [], "tenant_id": null}}
}
```

### Upgrading Hasura

If you are using managed database (e.g. Cloud SQL) and upgrading hasura image version to 1.3.3, make sure that hasura user is the owner of hdb_catalog schema.
You can find [more details in hasura documentation](https://hasura.io/docs/1.0/graphql/core/deployment/postgres-requirements.html#notes-for-managed-databases-aws-rds-gcp-cloud-sql-etc).

Moreover, double check if hasura user owns hdb_catalog.insert_event_log function.
To check functions ownership, run following SQL query:
```
SELECT proname, proowner::regrole FROM pg_proc WHERE pronamespace::regnamespace::text = 'hdb_catalog';
```

To change function ownership, run:
```
ALTER FUNCTION hdb_catalog.insert_event_log OWNER TO hasura;
```
