import pulumi
import pulumi_azure as azure
import pulumi_azuread as azuread
import pulumi_kubernetes as kubernetes
from pulumi_azure.containerservice import (
    KubernetesCluster,
    KubernetesClusterDefaultNodePoolArgs,
    KubernetesClusterServicePrincipalArgs,
)

from .base import Cluster, cluster_types, Database, database_types, get_password


class AzureBase:
    """
    Base Azure resources required for
    """

    _created: bool = False

    # Created resources
    resource_group: azure.core.ResourceGroup
    app: azuread.Application
    service_principal: azuread.ServicePrincipal
    service_principal_pwd: azuread.ServicePrincipalPassword

    def __init__(self):
        self.config = pulumi.Config("prefect-server-azure")

    def create_if_not_created(self):
        if not self._created:
            self.create()
            self._created = True

    def create(self):
        self.resource_group = azure.core.ResourceGroup("prefect-server-rg-")

        self.app = azuread.Application("prefect-server-app")

        self.service_principal = azuread.ServicePrincipal(
            "prefect-server-app-sp",
            application_id=self.app.application_id,
        )

        self.service_principal_pwd = azuread.ServicePrincipalPassword(
            "prefect-server-app-sp-pwd",
            service_principal_id=self.service_principal.id,
            end_date="2099-01-01T00:00:00Z",
            value=get_password("service-principal-password", self.config),
        )


# Singleton -- does not create any resources on init
azure_base = AzureBase()


@cluster_types.register("azure")
class AzureCluster(Cluster):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def create(self):
        # Create base resources
        azure_base.create_if_not_created()

        aks = KubernetesCluster(
            "prefect-cluster-",  # cannot be longer or it will exceed the char limit
            resource_group_name=azure_base.resource_group.name,
            kubernetes_version=self.k8s_version,
            dns_prefix="dns",
            service_principal=KubernetesClusterServicePrincipalArgs(
                client_id=azure_base.app.application_id,
                client_secret=azure_base.service_principal_pwd.value,
            ),
            default_node_pool=KubernetesClusterDefaultNodePoolArgs(
                name="type1",
                node_count=self.node_count,
                vm_size=azure_base.config.get("k8s-node-type"),
            ),
        )

        self._kubeconfig = aks.kube_config_raw


@database_types.register("azure")
class AzureDatabase(Database):
    server: azure.postgresql.Server

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def create(self):
        azure_base.create_if_not_created()

        self.server = azure.postgresql.Server(
            "prefect-db-",
            location=azure_base.resource_group.location,
            resource_group_name=azure_base.resource_group.name,
            administrator_login=self.username,
            administrator_login_password=self.password,
            sku_name="GP_Gen5_4",
            version="9.6",
            storage_mb=self.storage_mb,
            backup_retention_days=7,
            geo_redundant_backup_enabled=True,
            auto_grow_enabled=True,
            # TODO: Private IP connection
            public_network_access_enabled=True,
            ssl_enforcement_enabled=False,
            ssl_minimal_tls_version_enforced="TLS1_2",
        )

    @property
    def connection_username(self):
        return pulumi.Output.concat(
            self.server.administrator_login, "%40", self.server.fqdn
        )

    @property
    def connection_hostname(self):
        return self.server.fqdn
