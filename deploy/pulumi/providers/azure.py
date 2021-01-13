import pulumi
import pulumi_azure as azure
import pulumi_azuread as azuread
from pulumi_azure.containerservice import (
    KubernetesCluster,
    KubernetesClusterDefaultNodePoolArgs,
    KubernetesClusterServicePrincipalArgs,
    KubernetesClusterRoleBasedAccessControlArgs,
    KubernetesClusterNetworkProfileArgs,
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
    network: azure.network.VirtualNetwork
    private_subnet: azure.network.Subnet

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

        self.network = azure.network.VirtualNetwork(
            "prefect-vnet-",
            resource_group_name=self.resource_group.name,
            location=self.resource_group.location,
            address_spaces=["10.0.0.0/16"],
            subnets=[
                azure.network.VirtualNetworkSubnetArgs(
                    name="default",
                    address_prefix="10.0.1.0/24",
                )
            ],
        )

        self.private_subnet = azure.network.Subnet(
            "prefect-vnet-subnet-private-",
            resource_group_name=self.resource_group.name,
            virtual_network_name=self.network.name,
            address_prefixes=["10.0.2.0/24"],
            enforce_private_link_endpoint_network_policies=True,
            service_endpoints=["Microsoft.Sql"],
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
            kubernetes_version=azure_base.config.require("k8s-version"),
            dns_prefix="dns",
            service_principal=KubernetesClusterServicePrincipalArgs(
                client_id=azure_base.app.application_id,
                client_secret=azure_base.service_principal_pwd.value,
            ),
            default_node_pool=KubernetesClusterDefaultNodePoolArgs(
                name="basic",
                node_count=self.node_count,
                vm_size=azure_base.config.get("k8s-node-type"),
                vnet_subnet_id=azure_base.private_subnet.id,
            ),
            network_profile=KubernetesClusterNetworkProfileArgs(
                network_plugin="azure",
                service_cidr="10.10.0.0/16",
                dns_service_ip="10.10.0.10",
                docker_bridge_cidr="172.17.0.1/16",
            ),
        )

        self._kubeconfig = aks.kube_config_raw

        command_vars = pulumi.Output.all(aks.resource_group_name, aks.name)

        pulumi.export(
            "azure-kubeconfig-cmd",
            command_vars.apply(
                lambda var: (
                    "az aks get-credentials --resource-group {0} --name {1}".format(
                        *var
                    )
                )
            ),
        )


@database_types.register("azure")
class AzureDatabase(Database):
    server: azure.postgresql.Server
    endpoint: azure.privatelink.Endpoint
    database: azure.postgresql.Database

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def create(self):
        azure_base.create_if_not_created()

        self.server = azure.postgresql.Server(
            "prefect-sql-",
            location=azure_base.resource_group.location,
            resource_group_name=azure_base.resource_group.name,
            administrator_login=self.username,
            administrator_login_password=self.password,
            sku_name=azure_base.config.require("database-type"),
            version="11",
            storage_mb=self.storage_mb,
            backup_retention_days=7,
            geo_redundant_backup_enabled=False,
            auto_grow_enabled=False,
            public_network_access_enabled=True,
            ssl_enforcement_enabled=False,
        )

        vnet_rule = azure.postgresql.VirtualNetworkRule(
            "prefect-sql-vnet-",
            resource_group_name=azure_base.resource_group.name,
            server_name=self.server.name,
            subnet_id=azure_base.private_subnet.id,
            ignore_missing_vnet_service_endpoint=False,
        )

        self.database = azure.postgresql.Database(
            "prefect-db-",
            resource_group_name=azure_base.resource_group.name,
            server_name=self.server.name,
            charset="UTF8",
            collation="English_United States.1252",
            # Do not let the database resource be ready until the connection will be
            # allowed
            opts=pulumi.ResourceOptions(depends_on=[vnet_rule]),
        )

    @property
    def connection_username(self):
        return pulumi.Output.concat(
            self.server.administrator_login, "%40", self.server.fqdn
        )

    @property
    def connection_hostname(self):
        return self.server.fqdn

    @property
    def connection_dbname(self):
        return self.database.name

    @property
    def database_resource(self):
        return self.database
