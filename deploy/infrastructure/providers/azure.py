import pulumi
from pulumi import ResourceOptions
from pulumi_kubernetes import Provider
from pulumi_kubernetes.apps.v1 import Deployment, DeploymentSpecArgs
from pulumi_kubernetes.core.v1 import (
    ContainerArgs,
    PodSpecArgs,
    PodTemplateSpecArgs,
    Service,
    ServicePortArgs,
    ServiceSpecArgs,
)
from pulumi_kubernetes.meta.v1 import LabelSelectorArgs, ObjectMetaArgs
from pulumi_azure.core import ResourceGroup
from pulumi_azure.containerservice import (
    KubernetesCluster,
    KubernetesClusterDefaultNodePoolArgs,
    KubernetesClusterLinuxProfileArgs,
    KubernetesClusterLinuxProfileSshKeyArgs,
    KubernetesClusterServicePrincipalArgs,
)
from pulumi_azuread import Application, ServicePrincipal, ServicePrincipalPassword

from .base import Cluster, cluster_types


@cluster_types.register("azure")
class AzureCluster(Cluster):
    def __init__(self, *args, **kwargs):
        self.config = pulumi.Config("prefect-server-azure")
        super().__init__(*args, **kwargs)

    def create(self):
        # create a Resource Group and Network for all resources
        resource_group = ResourceGroup("prefect-server-rg")

        # create Azure AD Application for AKS
        app = Application("prefect-server-app")

        # create service principal for the application so AKS can act on behalf of the application
        sp = ServicePrincipal(
            "prefect-server-app-sp",
            application_id=app.application_id,
        )

        # create service principal password
        sppwd = ServicePrincipalPassword(
            "prefect-server-app-sp-pwd",
            service_principal_id=sp.id,
            end_date="2099-01-01T00:00:00Z",
            value=self.config.require_secret("service-principal-password"),
        )

        aks = KubernetesCluster(
            "prefect-cluster-",  # Name cannot be longer or it will exceed the char limit
            resource_group_name=resource_group.name,
            kubernetes_version=self.k8s_version,
            dns_prefix="dns",
            service_principal=KubernetesClusterServicePrincipalArgs(
                client_id=app.application_id, client_secret=sppwd.value
            ),
            default_node_pool=KubernetesClusterDefaultNodePoolArgs(
                name="type1",
                node_count=2,
                vm_size="Standard_B2ms",
            ),
        )

        k8s_provider = Provider(
            "k8s",
            kubeconfig=aks.kube_config_raw,
        )

        self._kubeconfig = aks.kube_config_raw
        self._k8s = k8s_provider
