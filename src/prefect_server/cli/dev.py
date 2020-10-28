import asyncio
import atexit
import os
import shutil
import signal
import subprocess
import time
from pathlib import Path

import click
import sqlalchemy
from click.testing import CliRunner

import prefect
import prefect_server
from prefect import models
from prefect_server import config


@click.group()
def dev():
    """
    Commands for developing Server
    """


def make_env(fname=None):
    PREFECT_ENV = dict()

    APOLLO_ENV = dict(
        HASURA_API_URL=f"http://hasura:{config.hasura.port}/v1alpha1/graphql",
        HASURA_WS_URL=f"ws://hasura:{config.hasura.port}/v1alpha1/graphql",
        PREFECT_API_URL=f"http://services:{config.services.graphql.port}{config.services.graphql.path}/",
        PREFECT_SERVER__TELEMETRY__ENABLED=(
            "true" if prefect_server.config.telemetry.enabled else "false"
        ),
    )

    POSTGRES_ENV = dict(
        POSTGRES_USER=config.database.username,
        POSTGRES_PASSWORD=config.database.password,
        POSTGRES_DB=config.database.name,
    )

    HASURA_ENV = dict(
        # replace localhost with postgres to use docker-compose dns
        HASURA_GRAPHQL_DATABASE_URL=config.hasura.db_url.replace(
            "localhost", "postgres"
        ),
    )

    ENV = os.environ.copy()
    ENV.update(**PREFECT_ENV, **APOLLO_ENV, **POSTGRES_ENV, **HASURA_ENV)

    if fname is not None:
        list_of_pairs = [
            f"{k}={repr(v)}" if "\n" in v else f"{k}={v}" for k, v in ENV.items()
        ]
        with open(fname, "w") as f:
            f.write("\n".join(list_of_pairs))
    return ENV.copy()


@dev.command()
@click.option(
    "--tag",
    "-t",
    help="The image/tag to use (for example, `dev` or `latest` [which is the master build])",
    default="dev",
)
@click.option(
    "--skip-pull",
    help="Pass this flag to skip pulling new images (if available)",
    is_flag=True,
)
@click.option(
    "--skip-upgrade",
    help="Pass this flag to skip upgrading the database to the most current version",
    is_flag=True,
)
def infrastructure(tag, skip_pull, skip_upgrade):
    """
    This command:
        - starts a PostgreSQL database
        - starts Hasura
    """
    docker_dir = Path(prefect_server.__file__).parents[2] / "docker" / "infrastructure"

    env = make_env()
    if "PREFECT_SERVER_TAG" not in env:
        env.update(PREFECT_SERVER_TAG=tag)

    proc = None
    try:
        if not skip_pull:
            subprocess.check_call(["docker-compose", "pull"], cwd=docker_dir, env=env)
        proc = subprocess.Popen(["docker-compose", "up"], cwd=docker_dir, env=env)

        # wait for db and then upgrade it to latest version
        if not skip_upgrade:
            engine = sqlalchemy.create_engine(config.database.connection_url)

            while True:
                try:
                    # simple query to see if database is alive
                    engine.execute("SELECT 1")
                    CliRunner().invoke(prefect_server.cli.database.upgrade, args=["-y"])
                    click.secho("Database upgraded.", fg="green")
                    break
                # trap error during the SELECT 1
                except sqlalchemy.exc.OperationalError as exc:
                    if "Connection refused" in str(exc):
                        click.echo(
                            "Database not ready yet. Waiting 1 second to retry upgrade."
                        )
                        time.sleep(1)
                    else:
                        click.secho(
                            "Database upgrade encountered fatal error:\n",
                            fg="red",
                            bold=True,
                        )
                        click.secho(str(exc) + "\n", fg="red")
                        raise

        click.echo(ascii_welcome())

        while True:
            time.sleep(0.5)
    except:
        click.secho(
            "Exception caught; killing services (press ctrl-C to force)",
            fg="white",
            bg="red",
        )
        subprocess.check_output(["docker-compose", "down"], cwd=docker_dir, env=env)
        if proc:
            proc.kill()
        raise


def is_process_group_empty(pgid: int):
    proc = subprocess.Popen(
        ["pgrep", "-g", str(pgid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    proc.wait()
    return proc.returncode != 0


def kill_process_group(proc, timeout: int = 3):
    try:
        pgid = os.getpgid(proc.pid)
        os.killpg(pgid, signal.SIGTERM)
        proc.terminate()

        for _ in range(timeout):
            if is_process_group_empty(pgid):
                return
            click.secho("Waiting for process group to exit...", fg="white", bg="blue")
            time.sleep(1)

        click.secho("Timeout while shutting down, killing!", fg="white", bg="red")
        os.killpg(pgid, signal.SIGKILL)
        proc.kill()
    except:
        pass


@dev.command()
@click.option(
    "--include", "-i", help="A comma-seperated list of serivces that should be run"
)
@click.option(
    "--exclude", "-e", help="A comma-seperated list of services that should not be run"
)
def services(include, exclude):
    """
    This command starts services
    """

    all_services = ["graphql", "towel", "apollo"]
    if not include:
        include = all_services
    else:
        include = include.split(",")
    if not exclude:
        exclude = ""
    run_services = sorted(set(include).difference(exclude.split(",")))

    click.secho(
        f"\n\nStarting Prefect Server services: {' '.join(run_services)}\n\n",
        fg="green",
    )

    procs = []
    for service in run_services:
        procs.append(
            subprocess.Popen(
                ["prefect-server", "services", service],
                env=make_env(),
                preexec_fn=os.setsid,
            )
        )
        atexit.register(kill_process_group, procs[-1])

    try:
        while True:
            time.sleep(1)
    except:
        click.secho("Exception caught; shutting down!", fg="white", bg="red")
        for proc in procs:
            kill_process_group(proc)


def config_to_dict(config):
    if isinstance(config, (list, tuple, set)):
        return type(config)([config_to_dict(d) for d in config])
    elif isinstance(config, prefect.configuration.Config):
        return dict({k: config_to_dict(v) for k, v in config.items()})
    return config


def set_nested(dictionary, path: str, value: str):
    path = path.split(".")
    for level in path[:-1]:
        dictionary = dictionary.setdefault(level, {})
    dictionary[path[-1]] = value


@dev.command()
def clear_data():
    """
    Clear data via cascades.
    """

    async def _clear_data():
        await models.Project.where().delete()

    asyncio.run(_clear_data())
    click.secho("Done!", fg="green")


@dev.command()
@click.option("-m", "--migration-message", required=True)
def generate_migration(migration_message):
    """
    Generates two files:
        - an alembic migration file that can be filled out to create a database migration
        - a hasura metadata archive that represents the hasura metadata at the START
            of the migration

    If the alembic migration ID is 'abcxyz' then the hasura migration will be named
    'metadata-abcxyz.py'. Note that this is a copy of the metadata PRIOR to running
    the migration, and will be used when DOWNGRADING through this alembic migration,
    or UPGRADING through the previous alembic migration.
    """
    # ensure this is called from the root server directory
    if Path(prefect_server.__file__).parents[2] != Path(os.getcwd()):
        raise click.ClickException(
            "generate-migration must be run from the root directory."
        )

    # create a new revision
    click.echo(
        subprocess.check_output(["alembic", "revision", "-m", migration_message])
    )

    # get the new revision id
    heads_output = subprocess.check_output(["alembic", "heads"])
    revision = heads_output.decode().split(" ", 1)[0]

    # copy metadata to a backup for corresponding revision
    hasura_migrations_path = "../../../services/hasura/migrations"
    backup_metadata_file = f"metadata-{revision}.yaml"
    backup_metadata_destination = os.path.abspath(
        os.path.join(
            prefect_server.__file__,
            hasura_migrations_path,
            "versions",
            backup_metadata_file,
        )
    )
    shutil.copy(
        os.path.abspath(
            os.path.join(
                prefect_server.__file__, hasura_migrations_path, "metadata.yaml"
            )
        ),
        backup_metadata_destination,
    )
    click.echo(f"Copied Hasura metadata to {backup_metadata_destination}")

    click.secho("Prefect Server migration generated!", fg="green")


def ascii_welcome():
    title = r"""
  _____  _____  ______ ______ ______ _____ _______    _____ ______ _______      ________ _____
 |  __ \|  __ \|  ____|  ____|  ____/ ____|__   __|  / ____|  ____|  __ \ \    / /  ____|  __ \
 | |__) | |__) | |__  | |__  | |__ | |       | |    | (___ | |__  | |__) \ \  / /| |__  | |__) |
 |  ___/|  _  /|  __| |  __| |  __|| |       | |     \___ \|  __| |  _  / \ \/ / |  __| |  _  /
 | |    | | \ \| |____| |    | |___| |____   | |     ____) | |____| | \ \  \  /  | |____| | \ \
 |_|    |_|  \_\______|_|    |______\_____|  |_|    |_____/|______|_|  \_\  \/   |______|_|  \_\
    """.lstrip(
        "\n"
    )

    message = f"""
{click.style(title, bold=True)}
{click.style(' | LOCAL INFRASTRUCTURE RUNNING', fg='blue', bold=True)}
    """

    return message
