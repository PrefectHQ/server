# Deployment of Prefect Server

## When to use

If you'd like to run Prefect Server on a single machine,  use `prefect server start` instead.

If you'd like to run Prefect Server for development, see the
[top-level README](...) instead.

If using an existing K8s cluster, you can install the Helm chart directly or use Pulumi as described below but disable the cluster and database creation.

If you are trying to run Prefect Server on a new K8s cluster on your cloud provider, this is the right place!


## What does this do

This tooling will create:

- A kubernetes cluster
- A cloud-provider specific managed Postgres instance
- Prefect Server services (via the Helm chart)

It manages the networking and basic setup for you with sane defaults.

## How to use

### Requirements

- Install [Pulumi CLI](https://www.pulumi.com/docs/get-started/)
- Set up a [Pulumi backend](https://www.pulumi.com/docs/intro/concepts/state/) with `pulumi login`. 
  
**Note** you do not have to use the Pulumi web service and can use `pulumi login --local` or a storage option of your choice to store the state. See their docs for all options.

Next, you'll have to install the requirements for your cloud provider.

####  Microsoft Azure

- Install the [Azure CLI](https://docs.microsoft.com/en-us/cli/azure/)
- Authenticate with `az login`

#### Google Cloud

- Install the [GCP CLI](...)
- Authenticate with `gcloud auth application-default login`

**Permissions:** To create a private connection in the VPC the ServiceNetworking API must be enabled, and your user must have the NetworkAdmin IAM role

### Configuring

We recommend making a *copy* of the default config file so you have a reference, e.g. 

```
cp Pulumi.default.config Pulumi.deploy.config
```

A Pulumi 'stack' must be initialized to track your deployment, this should have the same name as the config copy you've created

```
pulumi stack init deploy
```

Now you can modify the config file directly to set values or use `pulumi config set <key> <value>`. At a minimum, the `provider` value should be changed to the cloud provider you've chosen.

#### Secrets and passwords

If setting passwords, we recommend using `pulumi config set --secret <key> <value>` to ensure they are encrypted at rest. By default, all passwords are auto-generated (and are consequently commented out in the default config).

#### Config namespaces

- Prefect Server settings generic to all cloud providers (e.g. database name) are in the `prefect-server` namespace.
- Prefect Server settings specific to a single cloud provider (e.g. instance type) are in the `prefect-server-<provider_name>` namespaces.
- Pulumi cloud provider settings (e.g. region) are under the name of the provider, e.g. `gcp`. 


### Deploying

Run `pulumi up` to deploy the infrastructure and services, you will be prompted for confirmation before anything is created.

#### Outputs

Deployments create Pulumi outputs that can give information about the created stack. View them with `pulumi stack output <name>`

Available outputs include:
- **chart-override-values**: Values overriding helm chart defaults
- **kubeconfig**: The K8s cluster connection config. *Requires the `--show-secrets` flag for display*
