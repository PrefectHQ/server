import asyncio

import click
import distributed

import prefect
from prefect_server.services.agents.local_agent import LocalAgent


class DaskAgent(LocalAgent):
    """
    The DaskAgent runs flows in a Dask Cluster
    """

    def __init__(self, token, cluster_address=None, loop_interval=None):
        self.cluster_address = cluster_address
        self.dask_client = distributed.Client(self.cluster_address)
        super().__init__(token=token, loop_interval=loop_interval)

    def run_flow(self, environment, config, context, **kwargs):
        future = self.dask_client.submit(
            run_flow_in_worker,
            environment=environment,
            config=config,
            context=context,
            pure=False,
        )
        distributed.fire_and_forget(future)


def run_flow_in_worker(environment, config, context):
    with prefect.utilities.configuration.set_temporary_config(config):
        with prefect.context(context):
            environment.run()


@click.command()
@click.argument("token")
@click.option("--cluster", "-c", default=None)
def start(token: str, cluster: str) -> None:
    asyncio.run(DaskAgent(token=token, cluster_address=cluster).start())
