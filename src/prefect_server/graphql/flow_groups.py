from typing import Any

from graphql import GraphQLResolveInfo

from prefect_server import api
from prefect_server.utilities.graphql import mutation


@mutation.field("set_flow_group_default_parameters")
async def resolve_set_flow_group_default_parameters(
    obj: Any, info: GraphQLResolveInfo, input: dict
) -> dict:
    result = await api.flow_groups.set_flow_group_default_parameters(
        flow_group_id=input["flow_group_id"], parameters=input["parameters"]
    )
    return {"success": result}


@mutation.field("set_flow_group_labels")
async def resolve_set_flow_group_labels(
    obj: Any, info: GraphQLResolveInfo, input: dict
) -> dict:
    result = await api.flow_groups.set_flow_group_labels(
        flow_group_id=input["flow_group_id"], labels=input["labels"]
    )
    return {"success": result}


@mutation.field("set_flow_group_schedule")
async def resolve_set_flow_group_schedule(
    obj: Any, info: GraphQLResolveInfo, input: dict
) -> dict:
    cron_clocks = [
        {"type": "CronClock", **cron_clock}
        for cron_clock in input.get("cron_clocks", [])
    ]
    interval_clocks = []
    for interval_clock in input.get("interval_clocks", []):
        clock = {
            "type": "IntervalClock",
            # convert from seconds to microseconds
            "interval": interval_clock["interval"] * 1000000,
        }
        if interval_clock.get("parameter_defaults"):
            clock.update(
                {"parameter_defaults": interval_clock.get("parameter_defaults")}
            )
        interval_clocks.append(clock)

    clocks = cron_clocks + interval_clocks
    result = await api.flow_groups.set_flow_group_schedule(
        flow_group_id=input["flow_group_id"], clocks=clocks
    )
    return {"success": result}


@mutation.field("delete_flow_group_schedule")
async def resolve_delete_flow_group_schedule(
    obj: Any, info: GraphQLResolveInfo, input: dict
) -> dict:
    result = await api.flow_groups.delete_flow_group_schedule(
        flow_group_id=input["flow_group_id"]
    )
    return {"success": result}
