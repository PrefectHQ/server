from typing import List

from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Content, From, Mail, MimeType

from prefect_server import config

sendgrid_client = SendGridAPIClient(config.sendgrid.api_key)


def send_email(from_email: str, to_emails: List[str], subject: str, body: str) -> None:
    """
    Sends an HTML email

    Args:
        - from_email (str): the from address for the email
        - to_emails (List[str]) the destination(s) for the email
        - subject (str): the subject for the email
        - body (str): the body of the email - supports HTML

    """
    message = Mail(
        from_email=from_email,
        to_emails=to_emails,
        subject=subject,
    )
    message.content = Content(MimeType.text, body)
    if config.sendgrid.send_email:
        sendgrid_client.send(message)


def send_templated_email(
    from_email: str, to_emails: List[str], template_id: str, template_data: dict = None
) -> None:
    """
    Sends an email using one of our predefined Sendgrid templates.

    Args:
        - from_email (str): the from address for the email
        - to_emails (List[str]): the destination(s) for the email
        - template_id (str): the SendGrid template ID
        - template_data (dict): parameters

    """
    message = Mail(from_email=from_email, to_emails=to_emails)
    email_from = From(email=from_email, name="Prefect")
    message.from_email = email_from
    message.dynamic_template_data = template_data or {}
    message.template_id = template_id
    if config.sendgrid.send_email:
        sendgrid_client.send(message)
