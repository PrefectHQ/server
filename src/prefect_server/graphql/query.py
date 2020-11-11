import os
from typing import Any, Dict, List

import prefect
import prefect_server
from prefect.engine import state
from prefect_server.utilities import graphql


@graphql.query.field("hello")
async def resolve_hello(parent: Any, info):
    return "👋"


# the state hierarchy is a dictionary of {parent: [children]}, where each state appears
# as a parent and all of its ultimate subclasses are the children
state_hierarchy = {}  # type: Dict[str, List[str]]

# state info is a dictionary of {state: info}
state_info = {}  # type: Dict[str, Dict[str, Any]]

for obj in state.__dict__.values():
    if isinstance(obj, type) and issubclass(obj, state.State):

        # add parent class information
        for parent in obj.mro():
            if issubclass(parent, state.State):
                state_hierarchy.setdefault(parent.__name__, []).append(obj.__name__)

        # add state information
        state_info[obj.__name__] = {"color": obj.color}


@graphql.query.field("reference_data")
def resolve_reference(parent: Any, info):
    return {
        "state_hierarchy": state_hierarchy,
        "state_info": state_info,
    }


@graphql.query.field("api")
def resolve_reference(parent: Any, info):
    return {
        "backend": "SERVER",
        "mode": "normal",
        "version": os.getenv("PREFECT_SERVER_VERSION", prefect_server.__version__),
        "core_version": os.getenv("PREFECT_CORE_VERSION", prefect.__version__),
        "release_timestamp": os.getenv("RELEASE_TIMESTAMP"),
    }
