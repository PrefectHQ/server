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
