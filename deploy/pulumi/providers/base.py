import pulumi
from typing import Type, Dict, TypeVar, Generic, Callable, Optional, Any
from pulumi_kubernetes import Provider
from pulumi_random import RandomPassword

T = TypeVar("T")


def get_password(name: str, config: pulumi.Config = None) -> pulumi.Output:
    """
    Get a password from the config or generate a new random one
    """
    if not config:
        config = pulumi.Config()

    return (
        config.get_secret(name) or RandomPassword(name, length=20, special=True).result
    )


class Registry(Generic[T]):
    """
    Registry for implementations of a base class by cloud provider
    """

    def __init__(self, base_type: Type[T]):
        self._mapping: Dict[str, Type[T]] = {}
        self._base_type = base_type

    def _register(self, cloud_provider: str, cluster_type: Type[T]):
        if not issubclass(cluster_type, self._base_type):
            raise TypeError(
                f"Attempted to register {cluster_type} which is not a subclass of "
                f"{self._base_type}"
            )
        self._mapping[cloud_provider] = cluster_type

    def register(self, cloud_provider: str) -> Callable[[Type[T]], Type[T]]:
        def _decorator(cls: Type[T]) -> Type[T]:
            self._register(cloud_provider, cls)
            return cls

        return _decorator

    def get_instance(self, cloud_provider: str, *args: Any, **kwargs: Any) -> T:
        return self._mapping[cloud_provider](*args, **kwargs)


class Cluster:
    """
    Base class for Kubernetes cluster management
    """

    def __init__(self, k8s_version: str, node_count: int) -> None:
        self.k8s_version = k8s_version
        self.node_count = node_count
        self._provider: Optional[Provider] = None
        self._kubeconfig: Optional[str] = None

    def create(self) -> None:
        raise NotImplemented

    @property
    def provider(self) -> Provider:
        return Provider("k8s", kubeconfig=self.kubeconfig)

    @property
    def kubeconfig(self) -> str:
        if not self._kubeconfig:
            raise ValueError("kubeconfig has no value. Have you run `create()`?")
        return self._kubeconfig


class Database:
    """
    Base class for managed PostgreSQL management.
    """

    def __init__(
        self, username: str, password: str, database_name: str, storage_mb: int
    ):
        self.username = username
        self.password = password
        self.storage_mb = storage_mb
        self.database_name = database_name

    def create(self) -> None:
        raise NotImplemented

    @property
    def connection_username(self) -> pulumi.Output[str]:
        raise NotImplemented()

    @property
    def connection_hostname(self) -> pulumi.Output[str]:
        raise NotImplemented()

    @property
    def connection_dbname(self) -> pulumi.Output[str]:
        raise NotImplemented()

    @property
    def database_resource(self) -> Any:
        raise NotImplemented()


cluster_types: Registry[Cluster] = Registry(Cluster)
database_types: Registry[Database] = Registry(Database)
