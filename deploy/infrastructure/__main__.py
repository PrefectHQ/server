"""
Entrypoint for Prefect Server deployment with Pulumi
"""
import base64
from collections import defaultdict

import pulumi
from pulumi import ResourceOptions

import pulumi_kubernetes as kubernetes
from providers.base import cluster_types, database_types, get_password
from pulumi_kubernetes.helm.v3 import Chart, LocalChartOpts


# Utilities ----------------------------------------------------------------------------


def base64_encode(target: str) -> str:
    as_bytes = base64.b64encode(target.encode("utf-8"))
    return str(as_bytes, "utf-8")


def drop_namespace(target: str) -> str:
    parts = target.split("/")
    return parts[-1]


def nested_defaultdict():
    return defaultdict(nested_defaultdict)


# Configuration setup ------------------------------------------------------------------

config = pulumi.Config()
provider = config.require("provider")

# Define a mutable Resource options instance for the `helm_chart` so creating
# k8s is optional
chart_resources = ResourceOptions()

# Define helm chart overrides and fill with values from the config so users can override
# Helm values from Pulumi
chart_value_overrides = nested_defaultdict()
for key, val in config.get_object("services-values-override").values():
    chart_value_overrides[key] = val


# K8s cluster --------------------------------------------------------------------------


if config.require_bool("k8s-create"):
    # TODO: VPC/Availability settings

    # Get the K8s cluster builder for the provider
    cluster = cluster_types.get_instance(
        provider,
        k8s_version=config.require("k8s-version"),
        node_count=config.require_int("k8s-node-count"),
    )

    # Setup the cluster
    cluster.create()

    # Set the provider to this cluster
    chart_resources.provider = cluster.provider

    # Export the config for inspection
    pulumi.export("kubeconfig", cluster.kubeconfig)


# Postgres database --------------------------------------------------------------------

if config.require_bool("database-create"):

    # NOTE: Currently not working for Azure due to networking issues

    # Get the PostgreSQL database builder for the provider
    database = database_types.get_instance(
        provider,
        storage_mb=config.require_int("database-storage-mb"),
        username=config.require("database-username"),
        password=get_password("database-password"),
        database_name=config.require("database-name"),
    )

    # Setup the database
    database.create()

    # Add a secret to the cluster with the password
    pwd_secret = kubernetes.core.v1.Secret(
        "prefect-server-postgresql",
        data={"postgresql-password": database.password.apply(base64_encode)},
        opts=chart_resources,
    )

    # Point the helm chart to this database
    db_settings = chart_value_overrides["postgresql"]
    db_settings["useSubChart"] = False
    db_settings["postgresqlDatabase"] = database.connection_dbname
    db_settings["postgresqlUsername"] = database.connection_username
    db_settings["existingSecret"] = pwd_secret.id.apply(drop_namespace)
    db_settings["externalHostname"] = database.connection_hostname


# Services via helm chart --------------------------------------------------------------

if config.require_bool("services-create"):
    helm_chart = Chart(
        "prefect-server-helm",
        config=LocalChartOpts(
            path="../helm/prefect-server",
            values=chart_value_overrides,
        ),
        opts=chart_resources,
    )

    # TODO: Consider exporting results from the Helm chart as in
    #       https://github.com/pulumi/examples/blob/master/kubernetes-ts-helm-wordpress/index.ts
    #       since it appears the NOTES won't show

# Export the overrides - we cannot write this yaml to a file directly because it
# contains Pulumi Output objects and secrets.
pulumi.export("chart-value-overrides", chart_value_overrides)
