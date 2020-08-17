import os
import subprocess
import time
from pathlib import Path

import click

import prefect_server
from prefect_server import config

root_dir = Path(prefect_server.__file__).parents[2]
services_dir = root_dir / "src" / "prefect_server" / "services"


@click.group()
def services():
    """
    Commands for running Server services
    """


def run_proc_forever(proc):
    try:
        while True:
            time.sleep(0.5)
    except:
        click.secho("Exception caught; killing process.", fg="white", bg="red")
        proc.kill()
        raise


@services.command()
def graphql():
    """
    Start the Python GraphQL server
    """
    run_proc_forever(
        subprocess.Popen(
            ["python", services_dir / "graphql" / "server.py"],
            env=dict(os.environ, PREFECT_SERVER_VERSION="development"),
        )
    )


@services.command()
def towel():
    """
    Start the Server maintenance services
    """
    run_proc_forever(subprocess.Popen(["python", services_dir / "towel"]))


@services.command()
def apollo():
    """
    Start the Apollo GraphQL server
    """
    run_proc_forever(
        subprocess.Popen(
            ["npm", "run", "start"],
            cwd=root_dir / "services" / "apollo",
            env=dict(
                os.environ,
                PREFECT_SERVER_VERSION="development",
                HASURA_API_URL=config.hasura.graphql_url,
                HASURA_WS_URL=config.hasura.ws_url,
                PREFECT_API_URL=f"http://{config.services.graphql.host}:{config.services.graphql.port}{config.services.graphql.path}",
                PREFECT_SERVER__TELEMETRY__ENABLED=(
                    "true" if prefect_server.config.telemetry.enabled else "false"
                ),
            ),
        )
    )
