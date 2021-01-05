import pulumi
import pulumi_gcp as gcp
import textwrap

from .base import Cluster, cluster_types, Database, database_types, get_password


class GCPBase:
    """
    Base GCP resources required for
    """

    _created: bool = False

    # Created resources
    vpc: gcp.compute.Network
    private_ips: gcp.compute.GlobalAddress
    vpc_connection = gcp.servicenetworking.Connection

    def __init__(self):
        self.config = pulumi.Config("prefect-server-gcp")

    def create_if_not_created(self):
        if not self._created:
            self.create()
            self._created = True

    def create(self):
        self.vpc = gcp.compute.Network("prefect-server-vpc")
        self.private_ips = gcp.compute.GlobalAddress(
            "prefect-server-vpc-ips",
            purpose="VPC_PEERING",
            address_type="INTERNAL",
            prefix_length=16,
            network=self.vpc.id,
        )

        self.vpc_connection = gcp.servicenetworking.Connection(
            "prefect-server-vpc-conn",
            network=self.vpc.id,
            service="servicenetworking.googleapis.com",
            reserved_peering_ranges=[self.private_ips.name],
        )


# Singleton -- does not create any resources on init
gcp_base = GCPBase()


@cluster_types.register("gcp")
class GCPCluster(Cluster):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def create(self):
        # Create base resources
        gcp_base.create_if_not_created()

        k8s = gcp.container.Cluster(
            "prefect-cluster",
            initial_node_count=self.node_count,
            # TODO: Determine how to use the version properly
            # node_version=self.k8s_version,
            # min_master_version=self.k8s_version,
            master_auth=gcp.container.ClusterMasterAuthArgs(
                username="admin",
                password=get_password("k8s-admin-password", gcp_base.config),
            ),
            node_config=gcp.container.ClusterNodeConfigArgs(
                machine_type=gcp_base.config.require("k8s-node-type"),
                oauth_scopes=[
                    "https://www.googleapis.com/auth/compute",
                    "https://www.googleapis.com/auth/devstorage.read_only",
                    "https://www.googleapis.com/auth/logging.write",
                    "https://www.googleapis.com/auth/monitoring",
                ],
            ),
            ip_allocation_policy=gcp.container.ClusterIpAllocationPolicyArgs(
                services_ipv4_cidr_block="/16", cluster_ipv4_cidr_block="/14"
            ),
            network=gcp_base.vpc,
        )
        self._kubeconfig = self._generate_kubeconfig(k8s)

    @staticmethod
    def _generate_kubeconfig(k8s: gcp.container.Cluster) -> pulumi.Output[str]:
        # Package the K8s variables into a single output
        k8s_info = pulumi.Output.all(k8s.name, k8s.endpoint, k8s.master_auth)

        # Transform into a config
        return k8s_info.apply(
            lambda info: textwrap.dedent(
                """
                apiVersion: v1
                clusters:
                - cluster:
                    certificate-authority-data: {auth_cert}
                    server: https://{cluster_endpoint}
                  name: {qualified_name}
                contexts:
                - context:
                    cluster: {qualified_name}
                    user: {qualified_name}
                  name: {qualified_name}
                current-context: {qualified_name}
                kind: Config
                preferences: {{}}
                users:
                - name: {qualified_name}
                  user:
                    auth-provider:
                      config:
                        cmd-args: config config-helper --format=json
                        cmd-path: gcloud
                        expiry-key: '{{.credential.token_expiry}}'
                        token-key: '{{.credential.access_token}}'
                      name: gcp
                """.format(
                    auth_cert=info[2]["clusterCaCertificate"],
                    cluster_endpoint=info[1],
                    qualified_name="{project}_{zone}_{cluster_name}".format(
                        project=gcp.config.project,
                        zone=gcp.config.zone,
                        cluster_name=info[0],
                    ),
                )
            )
        )


@database_types.register("gcp")
class GCPDatabase(Database):
    """
    Creates a CloudSQL Postgres database with a private IP within the base VPC for
    connection.
    """

    instance: gcp.sql.DatabaseInstance
    database: gcp.sql.Database
    user: gcp.sql.User

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def create(self):
        gcp_base.create_if_not_created()

        self.instance = gcp.sql.DatabaseInstance(
            "prefect-db",
            region=gcp.config.region,
            settings=gcp.sql.DatabaseInstanceSettingsArgs(
                tier="db-f1-micro",
                disk_size=round(self.storage_mb / 1024),
                ip_configuration=gcp.sql.DatabaseInstanceSettingsIpConfigurationArgs(
                    private_network=gcp_base.vpc.id,
                    ipv4_enabled=False,
                ),
            ),
            deletion_protection=False,
            project=gcp.config.project,
            database_version="POSTGRES_11",
            # For the private vpc connection to work we need the private ips to have
            # been created successfully
            opts=pulumi.ResourceOptions(
                depends_on=[gcp_base.vpc_connection, gcp_base.private_ips]
            ),
        )

        self.database = gcp.sql.Database(self.database_name, instance=self.instance)

        self.user = gcp.sql.User(
            self.username, instance=self.instance.name, password=self.password
        )

    @property
    def connection_username(self):
        return self.user.name

    @property
    def connection_hostname(self):
        return self.instance.private_ip_address

    @property
    def connection_dbname(self):
        return self.database.name
