from unittest.mock import MagicMock

from prefect_server import config, utilities
from prefect_server.utilities.tests import set_temporary_config


def test_send_email_defaults_to_false():
    assert config.sendgrid.send_email is False


class TestSendTemplatedEmail:
    async def test_send_email_responds_to_config(self, monkeypatch):
        hook = MagicMock()
        monkeypatch.setattr("sendgrid.SendGridAPIClient.send", hook)

        utilities.email.send_templated_email(
            from_email="from-email-addr@prefect.io",
            to_emails=["to-email-addr@prefect.io"],
            template_id="test-template-id",
            template_data={"x": "y"},
        )
        assert hook.called is False

    async def test_sendgrid_treats_to_email_address_without_at_sign_as_name(
        self, monkeypatch
    ):
        """
        Sendgrid appears to parse `from` emails but not `to` emails
        """
        hook = MagicMock()
        monkeypatch.setattr("sendgrid.SendGridAPIClient.send", hook)

        with set_temporary_config("sendgrid.send_email", True):
            utilities.email.send_templated_email(
                from_email="from-email-addr",
                to_emails=["to-email-addr"],
                template_id=None,
            )
        mail = hook.call_args[0][0]
        assert len(mail.personalizations) == 1
        assert mail.personalizations[0].tos == [{"name": "to-email-addr"}]

    async def test_send_email_payload(self, monkeypatch):
        hook = MagicMock()
        monkeypatch.setattr("sendgrid.SendGridAPIClient.send", hook)

        with set_temporary_config("sendgrid.send_email", True):
            utilities.email.send_templated_email(
                from_email="from-email-addr@prefect.io",
                to_emails=["to-email-addr@prefect.io"],
                template_id="test-template-id",
                template_data={"x": "y"},
            )
        assert hook.called is True

        mail = hook.call_args[0][0]
        assert mail.from_email.email == "from-email-addr@prefect.io"
        assert len(mail.personalizations) == 1
        assert mail.personalizations[0].tos == [{"email": "to-email-addr@prefect.io"}]
        assert mail.template_id.template_id == "test-template-id"
        assert mail.personalizations[0].dynamic_template_data == {"x": "y"}


class TestSendEmail:
    async def test_send_email(self, monkeypatch):
        hook = MagicMock()
        monkeypatch.setattr("sendgrid.SendGridAPIClient.send", hook)

        body = "Don't Panic"
        with set_temporary_config("sendgrid.send_email", True):
            utilities.email.send_email(
                from_email="zaphod@prefect.io",
                to_emails=["ford@prefect.io"],
                subject="Testing",
                body=body,
            )
        assert hook.called is True

        mail = hook.call_args[0][0]
        assert mail.from_email.email == "zaphod@prefect.io"
        assert mail.personalizations[0].tos == [{"email": "ford@prefect.io"}]
        assert mail.subject.subject == "Testing"
        assert mail.contents[0].content == body

    async def test_send_email_responds_to_config(self, monkeypatch):
        hook = MagicMock()
        monkeypatch.setattr("sendgrid.SendGridAPIClient.send", hook)

        utilities.email.send_email(
            from_email="zaphod@prefect.io",
            to_emails=["ford@prefect.io"],
            subject="Testing",
            body="Don't Panic",
        )
        assert hook.called is False
