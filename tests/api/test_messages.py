import pendulum
import pytest

from prefect import api, models


class TestCreateUpdate:
    async def test_create_message(self, tenant_id):
        now = pendulum.now("utc")
        message_id = await api.messages.create_message(
            tenant_id=tenant_id,
            type="CLOUD_HOOK",
            text="This is a test",
            content=dict(text="This is a test."),
        )
        # confirm the message id is not none
        assert message_id is not None

        # confirm the message retrieved from the db matches what we'd expect
        message = await models.Message.where(id=message_id).first(
            {"created", "updated", "content", "type", "text", "read"}
        )
        assert message.created >= now
        assert message.updated >= now
        assert message.text == "This is a test"
        assert message.type == "CLOUD_HOOK"
        assert message.content == {"text": "This is a test."}
        assert message.read is False

    async def test_create_message_fails_with_invalid_type(self, tenant_id):
        with pytest.raises(ValueError, match="Invalid message type."):
            await api.messages.create_message(
                type="blah",
                content=dict(text="blah"),
                tenant_id=tenant_id,
            )


class TestMarkmessageAsRead:
    async def test_mark_message_as_read_placeholder(self, tenant_id):
        message_id = await api.messages.create_message(
            type="CLOUD_HOOK",
            text="Blah",
            content=dict(text="Blah"),
            tenant_id=tenant_id,
        )
        success = await api.messages.mark_message_as_read(message_id=message_id)

        assert success is True
        # confirm the message appears as we'd expect in the DB
        message = await models.Message.where(id=message_id).first({"read"})
        assert message.read is True

    async def test_mark_message_as_read_fails_if_none(self):
        with pytest.raises(ValueError, match="Invalid message ID."):
            await api.messages.mark_message_as_read(message_id=None)


class TestDeletemessage:
    async def test_delete_message(self, tenant_id):
        message_id = await api.messages.create_message(
            type="CLOUD_HOOK",
            text="Message",
            content=dict(text="Content"),
            tenant_id=tenant_id,
        )
        success = await api.messages.delete_message(message_id=message_id)
        assert success is True

        message = await models.Message.where(id=message_id).first()
        assert message is None

    async def test_delete_message_fails_if_none(self):
        with pytest.raises(ValueError, match="Invalid message ID."):
            await api.messages.delete_message(message_id=None)
