# Licensed under the Prefect Community License, available at
# https://www.prefect.io/legal/prefect-community-license

import datetime
import json
import uuid
from typing import List

import pendulum
import pydantic
import pytest
from asynctest import CoroutineMock
from box import Box
from prefect import models
from prefect.engine.state import Running, Scheduled
from prefect.utilities.graphql import EnumValue

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

    def test_primary_key_property(self):
        class Model(orm.HasuraModel):

            id: int
            custom_id: int

        class CustomModel(orm.HasuraModel):
            __primary_key__ = "custom_id"
            id: int
            custom_id: int

        assert Model(id=1, custom_id=2).primary_key == 1
        assert CustomModel(id=1, custom_id=2).primary_key == 2


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
        assert await models.Project.where(id=project_id).first()

    async def test_exists_false(self):
        assert not await models.Project.where(id=uuid.uuid4()).first()

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
        p1 = models.Project(name="p1")
        p2 = models.Project(name="p2")
        p3 = models.Project(name="p3")
        ids = await models.Project.insert_many([p1, p2, p3])
        assert len(ids) == 3
        assert all([await models.Project.where(id=i).first() for i in ids])

    async def test_insert_dict(self, project_id):
        p1 = dict(name="p1")
        p2 = dict(name="p2")
        p3 = dict(name="p3")
        ids = await models.Project.insert_many([p1, p2, p3])
        assert all([await models.Project.where(id=i).first() for i in ids])

    async def test_insert_dict_with_apply_schema(self, project_id):
        p1 = dict(name="p1")
        p2 = dict(name="p2")
        p3 = dict(name="p3")
        ids = await models.Project.insert_many([p1, p2, p3])
        assert all([await models.Project.where(id=i).first() for i in ids])

    async def test_get_more_than_100_objects(self, project_id):
        await models.Project.where().delete()
        await models.Project.insert_many(
            [{"name": str(uuid.uuid4())} for i in range(108)]
        )
        projects = await models.Project.where().get()
        assert len(projects) == 108


class TestModelQuery:
    @pytest.fixture
    async def project_ids(self):
        # delete all projects
        await models.Project.where({}).delete()

        p1 = dict(name="p1")
        p2 = dict(name="p2")
        p3 = dict(name="p3")
        return await models.Project.insert_many([p1, p2, p3])

    async def test_get(self, project_ids):
        projects = await orm.ModelQuery(model=models.Project).get()
        assert len(projects) == 3
        assert all([isinstance(p, models.Project) for p in projects])
        assert set(p.id for p in projects) == set(project_ids)

    async def test_get_selection_set(
        self,
        project_ids,
    ):

        projects = await orm.ModelQuery(model=models.Project).get(selection_set="name")
        assert set(p.name for p in projects) == {"p1", "p2", "p3"}

    async def test_get_limit(self, project_ids):
        projects = await orm.ModelQuery(model=models.Project).get(limit=2)
        assert len(projects) == 2

    async def test_first(self, project_ids):
        project = await orm.ModelQuery(model=models.Project).first()
        assert isinstance(project, models.Project)

    async def test_count(
        self,
        project_ids,
    ):
        assert await orm.ModelQuery(model=models.Project, where={}).count() == 3

    async def test_count_where(
        self,
        project_ids,
    ):
        assert (
            await models.Project.where(
                {
                    "name": {"_neq": "p2"},
                }
            ).count()
            == 2
        )

    async def test_update_set(
        self,
        project_ids,
    ):
        await models.Project.where({"id": {"_eq": project_ids[0]}}).update(
            set=dict(name="test")
        )
        names = set(p.name for p in await models.Project.where({}).get("name"))
        assert names == {"test", "p2", "p3"}

    async def test_update_increment(
        self,
        flow_run_id,
    ):
        fr1 = await models.FlowRun.where(id=flow_run_id).first({"version"})
        await models.FlowRun.where(id=flow_run_id).update(increment={"version": 5})
        fr2 = await models.FlowRun.where(id=flow_run_id).first({"version"})
        assert fr2.version == fr1.version + 5

    async def test_update_append(
        self,
        task_id,
    ):
        t1 = await models.Task.where(id=task_id).first({"tags"})
        await models.Task.where(id=task_id).update(append={"tags": "abc-xyz"})
        t2 = await models.Task.where(id=task_id).first({"tags"})
        assert len(t2.tags) == len(t1.tags) + 1
        assert t2.tags[-1] == "abc-xyz"

    async def test_update_prepend(
        self,
        task_id,
    ):
        t1 = await models.Task.where(id=task_id).first({"tags"})
        await models.Task.where(id=task_id).update(prepend={"tags": "abc-xyz"})
        t2 = await models.Task.where(id=task_id).first({"tags"})
        assert len(t2.tags) == len(t1.tags) + 1
        assert t2.tags[0] == "abc-xyz"

    async def test_update_delete_key_array(
        self,
        task_id,
    ):
        await models.Task.where(id=task_id).update(set={"tags": ["a", "b", "c", "d"]})
        await models.Task.where(id=task_id).update(delete_key={"tags": "c"})
        t1 = await models.Task.where(id=task_id).first({"tags"})
        assert t1.tags == ["a", "b", "d"]

    async def test_update_delete_elem_array(
        self,
        task_id,
    ):
        await models.Task.where(id=task_id).update(set={"tags": ["a", "b", "c", "d"]})
        await models.Task.where(id=task_id).update(delete_elem={"tags": 2})
        t1 = await models.Task.where(id=task_id).first({"tags"})
        assert t1.tags == ["a", "b", "d"]

    async def test_update_delete_key_obj(
        self,
        flow_run_id,
    ):
        await models.FlowRun.where(id=flow_run_id).update(
            set={"context": {"a": 1, "b": 2, "c": 3}}
        )
        await models.FlowRun.where(id=flow_run_id).update(delete_key={"context": "c"})
        fr = await models.FlowRun.where(id=flow_run_id).first({"context"})
        assert fr.context == {"a": 1, "b": 2}

    async def test_delete(
        self,
        project_ids,
    ):
        await models.Project.where({"id": {"_eq": project_ids[0]}}).delete()
        names = set(p.name for p in await models.Project.where({}).get("name"))
        assert names == {"p2", "p3"}


class TestAggregates:
    @pytest.fixture(autouse=True)
    async def flow_ids(self, tenant_id, project_id, project_id_2, flow_group_id):
        await models.Flow.where().delete()
        await models.Flow.insert_many(
            [
                dict(
                    tenant_id=tenant_id,
                    project_id=project_id,
                    name="a",
                    version=1,
                    flow_group_id=flow_group_id,
                ),
                dict(
                    tenant_id=tenant_id,
                    project_id=project_id,
                    name="b",
                    version=2,
                    flow_group_id=flow_group_id,
                ),
                dict(
                    tenant_id=tenant_id,
                    project_id=project_id_2,
                    name="a",
                    version=3,
                    flow_group_id=flow_group_id,
                ),
            ]
        )

    async def test_count(self):
        result = await models.Flow.where().count()
        assert result == 3

    async def test_count_where(self, project_id):
        result = await models.Flow.where({"project_id": {"_eq": project_id}}).count()
        assert result == 2

    async def test_count_distinct(self, project_id):
        result = await models.Flow.where().count(distinct_on=[EnumValue("name")])
        assert result == 2

    async def test_sum(self):
        result = await models.Flow.where().sum(["version"])
        assert result["version"] == 6

    async def test_sum_where(self):
        result = await models.Flow.where({"name": {"_eq": "a"}}).sum(["version"])
        assert result["version"] == 4

    async def test_max(self):
        result = await models.Flow.where().max(["version"])
        assert result["version"] == 3

    async def test_max_where(self):
        result = await models.Flow.where({"name": {"_eq": "b"}}).max(["version"])
        assert result["version"] == 2

    async def test_min(self):
        result = await models.Flow.where().min(["version"])
        assert result["version"] == 1

    async def test_min_where(self):
        result = await models.Flow.where({"name": {"_eq": "b"}}).min(["version"])
        assert result["version"] == 2



class TestRootFields:
    class TestModel(orm.HasuraModel):
        __hasura_type__ = "abc"
        __root_fields__ = {}

    class TestCustomModel(orm.HasuraModel):
        __hasura_type__ = "abc"
        __root_fields__ = {
            "select": "custom_select_xyz",
            "select_aggregate": "custom_select_aggregate_xyz",
            "insert": "custom_insert_xyz",
            "update": "custom_update_xyz",
            "delete": "custom_delete_xyz",
        }

    # --------------------
    # inferred root fields
    # --------------------

    async def test_get_select_root_field_graphql(self, monkeypatch):
        mock = CoroutineMock()
        monkeypatch.setattr("prefect_server.database.hasura.HasuraClient.execute", mock)
        graphql = await self.TestModel().where().get()
        mock.assert_called_once_with(
            query={"query": {"select: abc(where: {})": "id"}}, as_box=False
        )

    async def test_get_select_aggregate_root_field_graphql(self, monkeypatch):
        mock = CoroutineMock()
        monkeypatch.setattr("prefect_server.database.hasura.HasuraClient.execute", mock)
        graphql = await self.TestModel().where().count()
        mock.assert_called_once_with(
            {"query": {"count: abc_aggregate(where: {})": {"aggregate": "count"}}},
            as_box=False,
        )

    async def test_get_insert_root_field_graphql(self):
        graphql = await self.TestModel().insert_many([], run_mutation=False)
        assert next(iter(graphql["query"])).startswith("insert: insert_abc(")

    async def test_get_update_root_field_graphql(self):
        graphql = await self.TestModel().where().update(run_mutation=False)
        assert next(iter(graphql["query"])).startswith("update: update_abc(")

    async def test_get_delete_root_field_graphql(self):
        graphql = await self.TestModel().where().delete(run_mutation=False)
        assert next(iter(graphql["query"])).startswith("delete: delete_abc(")

    # --------------------
    # custom root fields
    # --------------------

    async def test_get_custom_select_root_field_graphql(self, monkeypatch):
        mock = CoroutineMock()
        monkeypatch.setattr("prefect_server.database.hasura.HasuraClient.execute", mock)
        graphql = await self.TestCustomModel().where().get()
        mock.assert_called_once_with(
            query={"query": {"select: custom_select_xyz(where: {})": "id"}},
            as_box=False,
        )

    async def test_get_custom_select_aggregate_root_field_graphql(self, monkeypatch):
        mock = CoroutineMock()
        monkeypatch.setattr("prefect_server.database.hasura.HasuraClient.execute", mock)
        graphql = await self.TestCustomModel().where().count()
        mock.assert_called_once_with(
            {
                "query": {
                    "count: custom_select_aggregate_xyz(where: {})": {
                        "aggregate": "count"
                    }
                }
            },
            as_box=False,
        )

    async def test_get_custom_insert_root_field_graphql(self):
        graphql = await self.TestCustomModel().insert_many([], run_mutation=False)
        assert next(iter(graphql["query"])).startswith("insert: custom_insert_xyz(")

    async def test_get_custom_update_root_field_graphql(self):
        graphql = await self.TestCustomModel().where().update(run_mutation=False)
        assert next(iter(graphql["query"])).startswith("update: custom_update_xyz(")
        # recover correct fields for non-root types
        assert graphql["variables"][0].type == "abc_bool_exp!"

    async def test_get_custom_delete_root_field_graphql(self):
        graphql = await self.TestCustomModel().where().delete(run_mutation=False)
        assert next(iter(graphql["query"])).startswith("delete: custom_delete_xyz(")
        # recover correct fields for non-root types
        assert graphql["variables"][0].type == "abc_bool_exp!"
