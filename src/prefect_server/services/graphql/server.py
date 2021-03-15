import os
from pathlib import Path

import uvicorn
from ariadne import load_schema_from_path, make_executable_schema
from ariadne.asgi import GraphQL
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse

import prefect_server
from prefect_server.graphql import extensions, scalars
from prefect_server.utilities.graphql import mutation, query
from prefect_server.utilities.logging import get_logger

logger = get_logger("GraphQL Server")
sdl = load_schema_from_path(Path(__file__).parents[2] / "graphql" / "schema")


schema = make_executable_schema(sdl, query, mutation, *scalars.resolvers)

path = prefect_server.config.services.graphql.path or "/"

if not path.endswith("/"):
    path += "/"

# The interaction of how Starlette mounts the GraphQL app appears to result in
# 404's when the path doesn't end in a trailing slash. This means GraphQL queries
# must have a trailing slash
if not path.endswith("/"):
    raise ValueError("GraphQL path must end with '/'")


app = Starlette()
app.router.redirect_slashes = False
app.mount(
    path,
    GraphQL(
        schema,
        debug=prefect_server.config.services.graphql.debug,
        extensions=[extensions.PrefectHeader],
    ),
)

app_version = os.environ.get("PREFECT_SERVER_VERSION") or "UNKNOWN"


@app.route("/health", methods=["GET"])
def health(request: Request) -> JSONResponse:
    """Health check for cloud monitoring"""
    return JSONResponse(dict(status="ok", version=app_version))


def _get_uvicorn_log_level():
    prefect_log_level = prefect_server.configuration.config["logging"]["level"]
    # Uvicorn log levels are lower case
    uvicorn_log_level = prefect_log_level.lower()
    if uvicorn_log_level in uvicorn.config.LOG_LEVELS:
        logger.info(f"Using uvicorn log level = {uvicorn_log_level!r}")
        return uvicorn_log_level
    else:
        logger.warning(
            f"{repr(uvicorn_log_level)} not a valid uvicorn log level, falling back on default."
        )
        return None


if __name__ == "__main__":
    uvicorn.run(
        app,
        host=prefect_server.config.services.graphql.host,
        port=prefect_server.config.services.graphql.port,
        log_level=_get_uvicorn_log_level(),
    )
