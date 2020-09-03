"""
Tests that updating rows in various table update the `updated` column
"""

from prefect import models


async def test_flow_updated(flow_id):
    obj = await models.Flow.where(id=flow_id).first({"updated"})
    await models.Flow.where(id=flow_id).update(set={"name": "new-name"})
    obj_2 = await models.Flow.where(id=flow_id).first({"updated"})
    assert obj_2.updated > obj.updated


async def test_task_updated(task_id):
    obj = await models.Task.where(id=task_id).first({"updated"})
    await models.Task.where(id=task_id).update(set={"name": "new-name"})
    obj_2 = await models.Task.where(id=task_id).first({"updated"})
    assert obj_2.updated > obj.updated


async def test_flow_run_updated(flow_run_id):
    obj = await models.FlowRun.where(id=flow_run_id).first({"updated"})
    await models.FlowRun.where(id=flow_run_id).update(set={"version": 2})
    obj_2 = await models.FlowRun.where(id=flow_run_id).first({"updated"})
    assert obj_2.updated > obj.updated


async def test_task_run_updated(task_run_id):
    obj = await models.TaskRun.where(id=task_run_id).first({"updated"})
    await models.TaskRun.where(id=task_run_id).update(set={"version": 2})
    obj_2 = await models.TaskRun.where(id=task_run_id).first({"updated"})
    assert obj_2.updated > obj.updated
