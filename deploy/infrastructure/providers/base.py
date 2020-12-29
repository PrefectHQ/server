from typing import Type
from pulumi_kubernetes import Provider


class Cluster:
    def __init__(self, k8s_version: str):
        self.k8s_version = k8s_version
        self._k8s: Provider = None
        self._kubeconfig: str = None

    def create(self):
        raise NotImplemented

    @property
    def k8s(self) -> Provider:
        if not self._k8s:
            raise ValueError("k8s has no value. Have you run `create()`?")
        return self._k8s

    @property
    def kubeconfig(self) -> str:
        if not self._kubeconfig:
            raise ValueError("kubeconfig has no value. Have you run `create()`?")
        return self._kubeconfig


class ClusterFactory:
    _cluster_types = {}

    def _register(self, provider: str, cluster_type: Type[Cluster]):
        self._cluster_types[provider] = cluster_type

    def register(self, provider: str) -> None:
        def _decorator(cls):
            self._register(provider, cls)
            return cls

        return _decorator

    def get_instance(self, provider: str, *args, **kwargs) -> Cluster:
        return self._cluster_types[provider](*args, **kwargs)


cluster_types = ClusterFactory()
