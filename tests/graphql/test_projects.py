import uuid

from prefect import api, models


class TestCreateProject:
    mutation = """
        mutation($input: create_project_input!){
            create_project(input: $input){
                id
            }
        }
    """

    async def test_create_project(self, run_query, tenant_id):
        result = await run_query(
            query=self.mutation,
            variables=dict(input=dict(tenant_id=tenant_id, name="test-gql")),
        )
        assert await models.Project.exists(result.data.create_project.id)
        project = await models.Project.where(id=result.data.create_project.id).first(
            {"name"}
        )
        assert project.name == "test-gql"

    async def test_create_project_with_description(self, run_query, tenant_id):
        result = await run_query(
            query=self.mutation,
            variables=dict(
                input=dict(
                    tenant_id=tenant_id, name="test-gql", description="test-description"
                )
            ),
        )
        project = await models.Project.where(id=result.data.create_project.id).first(
            {"name", "description"}
        )
        assert project.name == "test-gql"
        assert project.description == "test-description"

    async def test_create_project_with_duplicate_name(self, run_query, tenant_id):
        await run_query(
            query=self.mutation,
            variables=dict(input=dict(tenant_id=tenant_id, name="test-gql")),
        )
        result = await run_query(
            query=self.mutation,
            variables=dict(input=dict(tenant_id=tenant_id, name="test-gql")),
        )
        assert result.data.create_project is None
        assert "Uniqueness violation" in result.errors[0].message


class TestDeleteProject:
    mutation = """
        mutation($input: delete_project_input!){
            delete_project(input: $input){
                success
            }
        }
    """

    async def test_delete_project(self, run_query, project_id):
        result = await run_query(
            query=self.mutation,
            variables=dict(input=(dict(project_id=project_id))),
        )
        assert result.data.delete_project.success
        assert not await models.Project.exists(project_id)

    async def test_delete_project_bad_id(self, run_query, project_id):
        result = await run_query(
            query=self.mutation,
            variables=dict(input=(dict(project_id=str(uuid.uuid4())))),
        )
        assert not result.data.delete_project.success


class TestSetProjectName:
    mutation = """
        mutation($input: set_project_name_input!){
            set_project_name(input: $input){
                id
            }
        }
    """

    async def test_set_project_name(self, run_query, project_id):
        result = await run_query(
            query=self.mutation,
            variables=dict(input=(dict(project_id=project_id, name="foo-bar"))),
        )
        assert result.data.set_project_name.id == project_id
        project = await models.Project.where(id=project_id).first({"name"})
        assert project.name == "foo-bar"

    async def test_set_project_name_with_bad_project_id(
        self,
        run_query,
    ):
        result = await run_query(
            query=self.mutation,
            variables=dict(input=(dict(project_id=str(uuid.uuid4()), name="foo-bar"))),
        )
        assert "Update failed" in result.errors[0].message

    async def test_update_project_to_already_used_name_fails(
        self, run_query, project_id, tenant_id
    ):
        await api.projects.create_project(tenant_id=tenant_id, name="test-gql")
        result = await run_query(
            query=self.mutation,
            variables=dict(input=(dict(project_id=project_id, name="test-gql"))),
        )

        assert not result.data.set_project_name
        assert "Uniqueness violation" in result.errors[0].message


class TestSetProjectDescription:
    mutation = """
        mutation($input: set_project_description_input!){
            set_project_description(input: $input){
                id
            }
        }

    """

    async def test_set_project_description(self, run_query, project_id):
        result = await run_query(
            query=self.mutation,
            variables=dict(input=dict(project_id=project_id, description="foo-bar")),
        )
        assert result.data.set_project_description.id == project_id
        project = await models.Project.where(id=project_id).first({"description"})
        assert project.description == "foo-bar"

    async def test_set_project_description_with_bad_project_id(
        self,
        run_query,
    ):
        result = await run_query(
            query=self.mutation,
            variables=dict(
                input=dict(project_id=str(uuid.uuid4()), description="foo-bar")
            ),
        )
        assert "Update failed" in result.errors[0].message
