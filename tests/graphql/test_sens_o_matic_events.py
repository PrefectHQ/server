# import uuid
# from asyncio import sleep

# from prefect import api
# from prefect_server.database import models
# from prefect_server.utilities import context
# from prefect_server.utilities.tests import (
#     evaluate_delete_event_payload,
#     set_temporary_config,
# )


# class TestEmitDeleteEventFlows:
#     delete_flow_mutation = """
#         mutation($input: delete_flow_input!) {
#             delete_flow(input: $input) {
#                 success
#             }
#         }
#     """

#     async def test_event_is_emitted_when_deleting_flows(
#         self, sens_o_matic_httpx_mock, run_query, flow_id
#     ):
#         with set_temporary_config("env", "production"):
#             result = await run_query(
#                 query=self.delete_flow_mutation,
#                 variables=dict(input=dict(flow_id=flow_id)),
#             )

#         await sleep(0)
#         assert not await models.Flow.exists(flow_id)
#         evaluate_delete_event_payload(
#             table_name="flow", row_id=flow_id, post_mock=sens_o_matic_httpx_mock
#         )

#     async def test_event_is_not_emitted_when_failed_flow_delete(
#         self, sens_o_matic_httpx_mock, run_query, flow_id
#     ):
#         incorrect_uuid = str(uuid.uuid4())

#         with set_temporary_config("env", "production"):
#             result = await run_query(
#                 query=self.delete_flow_mutation,
#                 variables=dict(input=dict(flow_id=incorrect_uuid)),
#             )

#         await sleep(0)
#         assert not await models.Flow.exists(incorrect_uuid)
#         sens_o_matic_httpx_mock.assert_not_called()


# class TestEmitDeleteProjects:
#     mutation = """
#         mutation($input: delete_project_input!){
#             delete_project(input: $input){
#                 success
#             }
#         }
#     """

#     async def test_event_is_emitted_when_deleting_projects(
#         self, sens_o_matic_httpx_mock, run_query, project_id
#     ):
#         with set_temporary_config("env", "production"):
#             result = await run_query(
#                 query=self.mutation,
#                 variables=dict(input=(dict(project_id=project_id))),
#             )

#         assert result.data.delete_project.success
#         assert not await models.Project.exists(project_id)
#         evaluate_delete_event_payload(
#             table_name="project", row_id=project_id, post_mock=sens_o_matic_httpx_mock
#         )

#     async def test_event_is_not_emitted_when_failed_project_delete(
#         self, sens_o_matic_httpx_mock, run_query, project_id
#     ):
#         with set_temporary_config("env", "production"):
#             result = await run_query(
#                 query=self.mutation,
#                 variables=dict(input=(dict(project_id=project_id))),
#             )

#         await sleep(0)
#         assert await models.Project.exists(project_id) is True
#         sens_o_matic_httpx_mock.assert_not_called()


# class TestEmitDeleteMessages:
#     mutation = """
#         mutation($input: delete_message_input!) {
#             delete_message(input: $input) {
#                 success
#             }
#         }
#     """

#     async def test_event_is_emitted_when_deleting_messages(
#         self, sens_o_matic_httpx_mock, run_query, user_id
#     ):
#         message_id = await api.messages.create_message(
#             user_id=user_id, type="CLOUD_HOOK", text="Blah", content=dict(text="Blah"),
#         )

#         with set_temporary_config("env", "production"):
#             result = await run_query(
#                 query=self.mutation, variables=dict(input={"message_id": message_id}),
#             )

#         await sleep(0)
#         assert result.data.delete_message.success
#         update = await models.Message.where(id=message_id).first()
#         assert update is None

#         evaluate_delete_event_payload(
#             table_name="message", row_id=message_id, post_mock=sens_o_matic_httpx_mock
#         )

#     async def test_event_is_not_emitted_when_failed_message_delete(
#         self, sens_o_matic_httpx_mock, run_query,
#     ):
#         with set_temporary_config("env", "production"):
#             result = await run_query(
#                 query=self.mutation,
#                 variables=dict(input=(dict(message_id=str(uuid.uuid4())))),
#             )

#         await sleep(0)
#         sens_o_matic_httpx_mock.assert_not_called()
