import pendulum
import pytest

from prefect import api, models
from prefect_server import config


class TestArtifactCreate:
    async def test_create_artifact(self, tenant_id, task_run_id):
        artifact_id = await api.artifacts.create_task_run_artifact(
            task_run_id=task_run_id,
            tenant_id=tenant_id,
            kind="link",
            data={"link": "http"},
        )
        assert artifact_id

        artifact = await models.TaskRunArtifact.where(id=artifact_id).first(
            {"task_run_id", "kind", "data", "tenant_id"}
        )

        assert artifact.task_run_id == task_run_id
        assert artifact.tenant_id == tenant_id
        assert artifact.kind == "link"
        assert artifact.data == {"link": "http"}

    async def test_create_artifact_no_tenant_id(self, tenant_id, task_run_id):
        artifact_id = await api.artifacts.create_task_run_artifact(
            task_run_id=task_run_id,
            kind="link",
            data={"link": "http"},
        )
        assert artifact_id

        artifact = await models.TaskRunArtifact.where(id=artifact_id).first(
            {"task_run_id", "kind", "data", "tenant_id"}
        )
        task_run = await models.TaskRun.where(id=task_run_id).first({"tenant_id"})

        assert artifact.task_run_id == task_run_id
        assert artifact.tenant_id == task_run.tenant_id

    async def test_create_artifact_no_task_run_id(self):
        with pytest.raises(ValueError):
            await api.artifacts.create_task_run_artifact(
                task_run_id="",
                kind="link",
                data={"link": "http"},
            )

    async def test_create_artifact_no_task_run_found(self):
        with pytest.raises(ValueError):
            await api.artifacts.create_task_run_artifact(
                task_run_id="aaaa",
                kind="link",
                data={"link": "http"},
            )

    async def test_create_artifact_tenant_id_not_match(self, task_run_id):
        with pytest.raises(ValueError):
            await api.artifacts.create_task_run_artifact(
                task_run_id=task_run_id,
                kind="link",
                data={"link": "http"},
                tenant_id="aaaa",
            )

    async def test_create_two_artifacts(self, task_run_id):
        await api.artifacts.create_task_run_artifact(
            task_run_id=task_run_id,
            kind="link",
            data={"link": "http"},
        )

        await api.artifacts.create_task_run_artifact(
            task_run_id=task_run_id,
            kind="link",
            data={"link2": "http2"},
        )

        amount = await models.TaskRunArtifact.where(
            {"task_run_id": {"_eq": task_run_id}}
        ).count()
        assert amount == 2


class TestArtifactUpdate:
    async def test_update_artifact(self, tenant_id, task_run_id):
        artifact_id = await api.artifacts.create_task_run_artifact(
            task_run_id=task_run_id,
            tenant_id=tenant_id,
            kind="link",
            data={"link": "http"},
        )

        success = await api.artifacts.update_task_run_artifact(
            task_run_artifact_id=artifact_id, data={"link2": "http2"}
        )

        assert success

        artifact = await models.TaskRunArtifact.where(id=artifact_id).first(
            {"task_run_id", "kind", "data", "tenant_id"}
        )

        assert artifact.task_run_id == task_run_id
        assert artifact.tenant_id == tenant_id
        assert artifact.kind == "link"
        assert artifact.data == {"link2": "http2"}

        with pytest.raises(ValueError):
            await api.artifacts.update_task_run_artifact(
                task_run_artifact_id="",
                data={"link": "http"},
            )

        amount = await models.TaskRunArtifact.where(
            {"task_run_id": {"_eq": task_run_id}}
        ).count()
        assert amount == 1


class TestArtifactDelete:
    async def test_delete_artifact(self, tenant_id, task_run_id):
        artifact_id = await api.artifacts.create_task_run_artifact(
            task_run_id=task_run_id,
            tenant_id=tenant_id,
            kind="link",
            data={"link": "http"},
        )

        success = await api.artifacts.delete_task_run_artifact(
            task_run_artifact_id=artifact_id
        )

        assert success

        amount = await models.TaskRunArtifact.where(
            {"task_run_id": {"_eq": task_run_id}}
        ).count()
        assert amount == 0

        with pytest.raises(ValueError):
            await api.artifacts.delete_task_run_artifact(
                task_run_artifact_id="",
            )
