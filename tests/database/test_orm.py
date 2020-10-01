# Licensed under the Prefect Community License, available at
# https://www.prefect.io/legal/prefect-community-license


import datetime
import json
import uuid
from typing import List

import pendulum
import pydantic
import pytest
from box import Box

from prefect import models
from prefect.engine.state import Running, Scheduled
from prefect_server.database import orm


class TestModel:
    async def test_model_is_pydantic(self):
        assert issubclass(models.Project, pydantic.BaseModel)

    async def test_model_class_has_hasura_type(self):
        assert models.Project.__hasura_type__ == "project"

    async def test_model_handles_invalid_fields(self):
        class Test(orm.HasuraModel):
            a: str

        t = Test(a=1, b=2)
        assert not hasattr(t, "b")

    async def test_datetimes_automatically_converted_to_pendulum(self):
        class Test(orm.HasuraModel):
            dt: datetime.datetime

        t = Test(dt=datetime.datetime(2020, 1, 1))
        assert isinstance(t.dt, pendulum.DateTime)

    async def test_hms_interval_automatically_converted_to_timedelta(self):
        class Test(orm.HasuraModel):
            d: datetime.timedelta

        assert Test(d="3:2:1").d == datetime.timedelta(hours=3, minutes=2, seconds=1)

    async def test_postgres_interval_automatically_converted_to_timedelta(self):
        class Test(orm.HasuraModel):
            d: datetime.timedelta

        assert Test(d="1 day").d == datetime.timedelta(days=1)
        assert Test(d="1 day 03:00:00").d == datetime.timedelta(days=1, hours=3)
        assert Test(d="1 month 2 days 00:00:05").d == datetime.timedelta(
            days=32, seconds=5
        )

    async def test_to_hasura_dict_adds_data_key_on_insert(self):
        class Child(orm.HasuraModel):
            x: int

        class Parent(orm.HasuraModel):
            child: Child

        t = Parent(child=Child(x=1))

        assert t.to_hasura_dict() == {"child": {"x": 1}}
        assert t.to_hasura_dict(is_insert=True) == {"child": {"data": {"x": 1}}}

    async def test_to_hasura_dict_adds_data_key_and_list_on_insert(self):
        class Child(orm.HasuraModel):
            x: int

        class Parent(orm.HasuraModel):
            children: List[Child]

        t = Parent(children=[Child(x=1), Child(x=2)])

        assert t.to_hasura_dict() == {"children": [{"x": 1}, {"x": 2}]}
        assert t.to_hasura_dict(is_insert=True) == {
            "children": {"data": [{"x": 1}, {"x": 2}]}
        }

    async def test_to_hasura_dict_adds_data_key_on_insert_multiple_times(self):
        class Grandchild(orm.HasuraModel):
            x: int

        class Child(orm.HasuraModel):
            grandchildren: List[Grandchild]

        class Parent(orm.HasuraModel):
            child: Child

        t = Parent(child=Child(grandchildren=[Grandchild(x=1), Grandchild(x=2)]))

        assert t.to_hasura_dict() == {"child": {"grandchildren": [{"x": 1}, {"x": 2}]}}
        assert t.to_hasura_dict(is_insert=True) == {
            "child": {"data": {"grandchildren": {"data": [{"x": 1}, {"x": 2}]}}}
        }


class TestFields:
    async def test_UUIDString_is_a_string(self):
        class Test(orm.HasuraModel):
            id: orm.UUIDString

        t = Test(id=str(uuid.uuid4()))
        assert isinstance(t.id, str)

    async def test_UUIDString_raises_if_invalid(self):
        class Test(orm.HasuraModel):
            id: orm.UUIDString

        with pytest.raises(pydantic.ValidationError):
            Test(id=1)

        with pytest.raises(pydantic.ValidationError):
            Test(id=uuid.uuid4())

        with pytest.raises(pydantic.ValidationError):
            Test(id="abc")

    async def test_pendulum_types_are_serializable(self):
        class Test(orm.HasuraModel):
            dt: pendulum.DateTime
            p: pendulum.Period

        t1 = pendulum.now("UTC")
        t2 = t1.subtract(hours=1)
        t = Test(dt=t1, p=t1 - t2)
        assert json.loads(t.json()) == {
            "dt": str(t1),
            "p": str((t1 - t2).total_seconds()),
        }


class TestORM:
    async def test_insert(self, project_id):
        id = await models.Project(name="test").insert()
        # the resut is the ID
        assert uuid.UUID(id)

    async def test_nested_insert_array(self, flow_id):
        """ insert nested objects as an array"""
        flow_run_id = await models.FlowRun(
            flow_id=flow_id,
            labels=[],
            states=[
                models.FlowRunState(state="test", serialized_state={}),
                models.FlowRunState(state="test", serialized_state={}),
            ],
        ).insert()

        assert (
            await models.FlowRunState.where(
                {"flow_run_id": {"_eq": flow_run_id}}
            ).count()
            == 2
        )

    async def test_nested_insert_array_dicts(self, flow_id):
        """ insert nested objects as an array"""
        flow_run_id = await models.FlowRun(
            flow_id=flow_id,
            labels=[],
            states=[
                dict(state="test", serialized_state={}),
                dict(state="test", serialized_state={}),
            ],
        ).insert()

        assert (
            await models.FlowRunState.where(
                {"flow_run_id": {"_eq": flow_run_id}}
            ).count()
            == 2
        )

    async def test_insert_selection_set(self):
        result = Box(
            await models.Project(name="test").insert(
                selection_set={
                    "affected_rows": True,
                    "returning": {"created", "name"},
                }
            )
        )
        assert result.affected_rows == 1
        assert result.returning.created
        assert result.returning.name == "test"

    async def test_insert_with_missing_fields(self):
        with pytest.raises(ValueError) as exc:
            await models.Project().insert()
        assert "null value in column" in str(exc.value)

    async def test_duplicate_insert(self):
        id = await models.Project(name="test").insert()
        with pytest.raises(ValueError):
            await models.Project(id=id, name="test-2").insert()

    async def test_get_insert_graphql(self):
        graphql = await models.Project().insert(alias="x", run_mutation=False)
        assert isinstance(graphql, dict)
        assert set(graphql) == {"query", "variables"}
        assert next(iter(graphql["query"])).startswith("x: insert_project(")

    async def test_delete(self, project_id):
        assert await models.Project(id=project_id).delete()

    async def test_delete_returns_false_is_failed(self):
        assert not await models.Project(id=str(uuid.uuid4())).delete()

    async def test_delete_runs_immediately(self, project_id):
        assert await models.Project(id=project_id).delete()
        assert not await models.Project(id=project_id).delete()

    async def test_delete_selection_set(self, project_id):
        result = await models.Project(id=project_id).delete(
            selection_set="returning { id }"
        )
        assert result.returning[0].id == project_id

    async def test_delete_without_id_fails(self):
        with pytest.raises(TypeError) as exc:
            await models.Project().delete()
        assert "`where`" in str(exc.value)

    async def test_get_delete_graphql(self):
        graphql = await models.Project(id=str(uuid.uuid4())).delete(
            alias="x", run_mutation=False
        )
        assert isinstance(graphql, dict)
        assert set(graphql) == {"query", "variables"}
        assert next(iter(graphql["query"])).startswith("x: delete_project(")

    async def test_exists(self, project_id):
        assert await models.Project.exists(project_id)

    async def test_exists_false(self):
        assert not await models.Project.exists(uuid.uuid4())

    async def test_where_is_modelquery(self):
        assert isinstance(models.Project.where(), orm.ModelQuery)

    async def test_where_with_no_args_selects_all(self):
        assert models.Project.where().where == {}

    async def test_where_assigns_model_and_where(self):
        q = models.Project.where(dict(x=1))
        assert q.model is models.Project
        assert q.where == dict(x=1)

    async def test_where_with_id(self, project_id):
        q = models.Project.where(id=project_id)
        assert q.where == {"id": {"_eq": project_id}}

    async def test_where_with_id_none_fails(self):
        with pytest.raises(ValueError):
            models.Project.where(id=None)

    async def test_where_with_where(self, project_id):
        q = models.Project.where(where={"id": {"_in": [project_id]}})
        assert q.where == {"id": {"_in": [project_id]}}

    async def test_insert_many(self, project_id):
        f1 = models.Project(name="f1")
        f2 = models.Project(name="f2")
        f3 = models.Project(name="f3")
        ids = await models.Project.insert_many([f1, f2, f3])
        assert len(ids) == 3
        assert all([await models.Project.exists(i) for i in ids])

    async def test_insert_dict(self, project_id):
        f1 = dict(name="f1")
        f2 = dict(name="f2")
        f3 = dict(name="f3")
        ids = await models.Project.insert_many([f1, f2, f3])
        assert all([await models.Project.exists(i) for i in ids])

    async def test_insert_dict_with_apply_schema(self, project_id):
        f1 = dict(name="f1")
        f2 = dict(name="f2")
        f3 = dict(name="f3")
        ids = await models.Project.insert_many([f1, f2, f3])
        assert all([await models.Project.exists(i) for i in ids])

    async def test_get_more_than_100_objects(self, project_id):
        await models.Project.where().delete()
        await models.Project.insert_many(
            [{"name": str(uuid.uuid4())} for i in range(108)]
        )
        flows = await models.Project.where().get()
        assert len(flows) == 108


class TestModelQuery:
    @pytest.fixture
    async def flow_ids(self):
        # delete default flows
        await models.Project.where({}).delete()

        f1 = dict(name="f1")
        f2 = dict(name="f2")
        f3 = dict(name="f3")
        return await models.Project.insert_many([f1, f2, f3])

    async def test_get(self, flow_ids):
        flows = await orm.ModelQuery(model=models.Project).get()
        assert len(flows) == 3
        assert all([isinstance(p, models.Project) for p in flows])
        assert set(p.id for p in flows) == set(flow_ids)

    async def test_get_selection_set(
        self,
        flow_ids,
    ):

        flows = await orm.ModelQuery(model=models.Project).get(selection_set="name")
        assert set(p.name for p in flows) == {"f1", "f2", "f3"}

    async def test_get_limit(self, flow_ids):
        flows = await orm.ModelQuery(model=models.Project).get(limit=2)
        assert len(flows) == 2

    async def test_first(self, flow_ids):
        flow = await orm.ModelQuery(model=models.Project).first()
        assert isinstance(flow, models.Project)

    async def test_count(
        self,
        flow_ids,
    ):
        assert await orm.ModelQuery(model=models.Project, where={}).count() == 3

    async def test_count_where(
        self,
        flow_ids,
    ):
        assert (
            await models.Project.where(
                {
                    "name": {"_neq": "f2"},
                }
            ).count()
            == 2
        )

    async def test_update(
        self,
        flow_ids,
    ):
        await models.Project.where({"id": {"_eq": flow_ids[0]}}).update(
            set=dict(name="test")
        )
        names = set(p.name for p in await models.Project.where({}).get("name"))
        assert names == {"test", "f2", "f3"}

    async def test_delete(
        self,
        flow_ids,
    ):
        await models.Project.where({"id": {"_eq": flow_ids[0]}}).delete()
        names = set(p.name for p in await models.Project.where({}).get("name"))
        assert names == {"f2", "f3"}


class TestRunModels:
    @pytest.mark.parametrize(
        "state",
        [
            Running(message="running", result=1),
            Scheduled(message="scheduled", result=1, start_time=pendulum.now()),
        ],
    )
    async def test_flow_run_fields_from_state(self, state):
        dt = pendulum.now()
        info = models.FlowRunState.fields_from_state(state)

        assert info["state"] == type(state).__name__
        assert info["timestamp"] > dt
        assert info["message"] == state.message
        assert info["result"] == state.result
        assert info["serialized_state"] == state.serialize()

    @pytest.mark.parametrize(
        "state",
        [
            Running(message="running", result=1),
            Scheduled(message="scheduled", result=1, start_time=pendulum.now()),
        ],
    )
    async def test_task_run_fields_from_state(self, state):
        dt = pendulum.now()
        info = models.TaskRunState.fields_from_state(state)

        assert info["state"] == type(state).__name__
        assert info["timestamp"] > dt
        assert info["message"] == state.message
        assert info["result"] == state.result
        assert info["serialized_state"] == state.serialize()
