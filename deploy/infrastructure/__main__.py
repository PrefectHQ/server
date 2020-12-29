"""
Entrypoint for Prefect Server deployment with Pulumi
"""

import pulumi
from pulumi import ResourceOptions
from providers.base import cluster_types
from pulumi_kubernetes.helm.v3 import Chart, LocalChartOpts


# from pulumi_azure import core, storage

config = pulumi.Config()
provider = config.require("provider")

# Define a mutable Resource options instance for the `helm_chart` so creating
# k8s is optional
chart_resources = ResourceOptions()

if config.require_bool("create-k8s-cluster"):
    # TODO: VPC/Availability settings

    # Get the K8s cluster builder for the provider
    cluster = cluster_types.get_instance(
        provider, k8s_version=config.require("k8s-version")
    )

    # Setup the cluster
    cluster.create()

    # Set the provider to this cluster
    chart_resources.provider = cluster.k8s

    # Export the config for inspection
    pulumi.export("kubeconfig", cluster.kubeconfig)


if config.require_bool("create-managed-postgres"):
    # TODO: Setup basic deployment in Azure then other providers
    # CloudSQL and such, we'll need to pass the config to the Helm chart
    pass


# Deploy our helm chart to the K8s cluster
# TODO: Add passing of Helm config overrides from the Pulumi config
helm_chart = Chart(
    "prefect-server-helm",
    LocalChartOpts(
        path="../helm/prefect-server",
    ),
    chart_resources,
)
