from prefect import api, models


class TestMarkUpdatesAsRead:
    mutation = """
        mutation($input: mark_message_as_read_input!) {
            mark_message_as_read(input: $input) {
                success
            }
        }
    """

    async def test_mark_message_as_read(self, run_query, tenant_id):
        message_id = await api.messages.create_message(
            type="CLOUD_HOOK",
            text="Blah",
            content=dict(text="Blah"),
            tenant_id=tenant_id,
        )
        # mark it as read
        result = await run_query(
            query=self.mutation, variables=dict(input={"message_id": message_id})
        )
        # confirm the resulting payload looks correct
        assert result.data.mark_message_as_read.success is True
        # confirm the resulting DB state looks correct
        update = await models.Message.where(id=message_id).first({"read"})
        assert update.read is True


class TestMarkUpdatesAsUnread:
    mutation_mark_as_read = """
        mutation($input: mark_message_as_read_input!) {
            mark_message_as_read(input: $input) {
                success
            }
        }
    """

    mutation_mark_as_unread = """
        mutation($input: mark_message_as_unread_input!) {
            mark_message_as_unread(input: $input) {
                success
            }
        }
    """

    async def test_mark_message_as_unread(self, run_query, tenant_id):
        message_id = await api.messages.create_message(
            type="CLOUD_HOOK",
            text="Blah",
            content=dict(text="Blah"),
            tenant_id=tenant_id,
        )

        update = await models.Message.where(id=message_id).first({"read"})
        assert update.read is False

        # mark it as read
        await run_query(
            query=self.mutation_mark_as_read,
            variables=dict(input={"message_id": message_id}),
        )

        update = await models.Message.where(id=message_id).first({"read"})
        assert update.read is True

        # mark it as unread
        result = await run_query(
            query=self.mutation_mark_as_unread,
            variables=dict(input={"message_id": message_id}),
        )

        # confirm the resulting payload looks correct
        assert result.data.mark_message_as_unread.success is True
        # confirm the resulting DB state looks correct
        update = await models.Message.where(id=message_id).first({"read"})
        assert update.read is False


class TestDeleteUpdate:
    mutation = """
        mutation($input: delete_message_input!) {
            delete_message(input: $input) {
                success
            }
        }
    """

    async def test_delete_message(self, run_query, tenant_id):
        message_id = await api.messages.create_message(
            type="CLOUD_HOOK",
            text="Blah",
            content=dict(text="Blah"),
            tenant_id=tenant_id,
        )
        result = await run_query(
            query=self.mutation, variables=dict(input={"message_id": message_id})
        )
        # confirm the payload looks as we'd expect it to
        assert result.data.delete_message.success
        # confirm the item is no longer in the database
        update = await models.Message.where(id=message_id).first()
        assert update is None
