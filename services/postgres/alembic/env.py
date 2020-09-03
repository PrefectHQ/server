import logging
import os
from logging.config import fileConfig

import click
from alembic import context
from sqlalchemy import engine_from_config, pool

import prefect_server

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
target_metadata = None

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.

# overwrite the config sqlalchemy.url that is usually set in alembic.ini
config.set_main_option("sqlalchemy.url", prefect_server.config.database.connection_url)


def run_migrations_offline():
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def apply_hasura_metadata(context):
    script = context.script.get_revision(context.get_context().get_current_revision())
    if not script:
        return

    # if the requestied alembic migration is `head`, use `metadata.yaml`
    if script.revision == context.script.get_current_head():
        hasura_revision = None

    # otherwise, we need to load the hasura metadata that was archived when
    # the NEXT alembic migration was created.
    else:
        hasura_revision = list(script.nextrev)[0]

    # attempt to load the corresponding hasura metadata
    metadata_path = os.path.join(__file__, "../../../hasura/migrations")
    metadata = os.path.abspath(
        os.path.join(metadata_path, "versions", f"metadata-{hasura_revision}.yaml")
    )

    logging.info("Applying Hasura metadata...")
    if os.path.exists(metadata):
        # apply matching metadata
        prefect_server.cli.hasura.apply_hasura_metadata(metadata_path=metadata)
    else:
        # apply current metadata
        prefect_server.cli.hasura.apply_hasura_metadata(metadata_path=None)


def run_migrations_online():
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """

    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():

            context.run_migrations()

        if context.get_x_argument(as_dictionary=True).get("apply_hasura_metadata"):
            apply_hasura_metadata(context)


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
