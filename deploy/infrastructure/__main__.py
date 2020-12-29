"""
Entrypoint for Prefect Server deployment with Pulumi
"""

import pulumi

from providers.base import cluster_types
from pulumi_kubernetes.helm.v3 import Chart, LocalChartOpts


# from pulumi_azure import core, storage

config = pulumi.Config()
provider = config.require("provider")


# Get the K8s cluster builder for the provider
cluster = cluster_types.get_instance(
    provider, k8s_version=config.require("k8s_version")
)

# Setup the cluster
cluster.create()

# Deploy our helm chart
helm_chart = Chart(
    "prefect-server-helm",
    LocalChartOpts(
        path="../helm/prefect-server",
    ),
    pulumi.ResourceOptions(
        provider=cluster.k8s,
    ),
)

pulumi.export("kubeconfig", cluster.kubeconfig)
