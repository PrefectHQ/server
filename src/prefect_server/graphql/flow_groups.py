import pendulum
from typing import Any

from graphql import GraphQLResolveInfo

from prefect import api
from prefect_server.utilities.graphql import mutation


@mutation.field("delete_flow_group")
async def resolve_delete_flow_group(
    obj: Any, info: GraphQLResolveInfo, input: dict
) -> dict:
    return {
        "success": await api.flow_groups.delete_flow_group(
            flow_group_id=input["flow_group_id"]
        )
    }


@mutation.field("set_flow_group_default_parameters")
async def resolve_set_flow_group_default_parameters(
    obj: Any, info: GraphQLResolveInfo, input: dict
) -> dict:
    result = await api.flow_groups.set_flow_group_default_parameters(
        flow_group_id=input["flow_group_id"], parameters=input["parameters"]
    )
    return {"success": result}


@mutation.field("set_flow_group_description")
async def resolve_set_flow_group_description(
    obj: Any, info: GraphQLResolveInfo, input: dict
) -> dict:
    result = await api.flow_groups.set_flow_group_description(
        flow_group_id=input["flow_group_id"], description=input.get("description")
    )
    return {"success": result}


@mutation.field("set_flow_group_labels")
async def resolve_set_flow_group_labels(
    obj: Any, info: GraphQLResolveInfo, input: dict
) -> dict:
    result = await api.flow_groups.set_flow_group_labels(
        flow_group_id=input["flow_group_id"], labels=input.get("labels")
    )
    return {"success": result}


@mutation.field("set_flow_group_run_config")
async def resolve_set_flow_group_run_config(
    obj: Any, info: GraphQLResolveInfo, input: dict
) -> dict:
    result = await api.flow_groups.set_flow_group_run_config(
        flow_group_id=input["flow_group_id"], run_config=input.get("run_config")
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
        flow_group_id=input["flow_group_id"],
        clocks=clocks,
        timezone=input.get("timezone"),
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
