import logging
from integrations.base import BaseClient
from config.settings import settings

logger = logging.getLogger("outreach_pipeline")

class BrevoClient(BaseClient):
    """Client for Brevo API v3 to send personalized cold outreach emails."""
    
    def __init__(self):
        super().__init__(settings.BREVO_API_URL, settings.BREVO_API_KEY)

    def send_email(self, to_email: str, to_name: str, subject: str, html_content: str) -> str:
        """
        Send a personalized HTML email via Brevo.
        Returns the message ID on success.
        """
        to_email = to_email.strip()
        to_name = to_name.strip()
        subject = subject.strip()
        
        sender_email = settings.BREVO_SENDER_EMAIL
        sender_name = settings.BREVO_SENDER_NAME
        
        if settings.is_dry_run:
            logger.info("[Mock] Sending email via Brevo:")
            logger.info(f"  From: {sender_name} <{sender_email}>")
            logger.info(f"  To: {to_name} <{to_email}>")
            logger.info(f"  Subject: {subject}")
            logger.info(f"  HTML Content Preview: {html_content[:150]}...")
            return "mock-message-id-123456789"

        logger.info(f"Sending real email to {to_name} <{to_email}> via Brevo...")
        headers = {
            "api-key": self.api_key,
            "accept": "application/json"
        }
        
        payload = {
            "sender": {
                "name": sender_name,
                "email": sender_email
            },
            "to": [
                {
                    "email": to_email,
                    "name": to_name
                }
            ],
            "subject": subject,
            "htmlContent": html_content
        }
        
        try:
            # POST /smtp/email
            response = self._send_request(
                method="POST",
                path="/smtp/email",
                headers=headers,
                json_data=payload
            )
            
            message_id = response.get("messageId", "")
            if message_id:
                logger.info(f"Email successfully sent. Message ID: {message_id}")
            else:
                logger.warning(f"Email sent, but no messageId was returned in response: {response}")
            return message_id
            
        except Exception as e:
            logger.error(f"Failed to send email via Brevo to {to_email}: {e}")
            raise e
