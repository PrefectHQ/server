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
        extensions=[extensions.PrefectHeader, extensions.PrefectConcurrencyLimiter],
    ),
)

app_version = os.environ.get("PREFECT_SERVER_VERSION") or "UNKNOWN"


@app.route("/health", methods=["GET"])
def health(request: Request) -> JSONResponse:
    """Health check for cloud monitoring"""
    return JSONResponse(dict(status="ok", version=app_version))


if __name__ == "__main__":
    uvicorn.run(
        app,
        host=prefect_server.config.services.graphql.host,
        port=prefect_server.config.services.graphql.port,
    )
