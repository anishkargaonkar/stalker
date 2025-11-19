"""
Email Sender Module - Handles actual email delivery
Supports multiple providers: SMTP, SendGrid, etc.
"""

import smtplib
import asyncio
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, List, Dict, Any
import logging
from datetime import datetime

try:
    import sendgrid
    from sendgrid.helpers.mail import Mail, Email, To, Content
    SENDGRID_AVAILABLE = True
except ImportError:
    SENDGRID_AVAILABLE = False

try:
    import boto3
    from botocore.exceptions import BotoCoreError, ClientError
    SES_AVAILABLE = True
except ImportError:
    SES_AVAILABLE = False

import aiosmtplib
from email_validator import validate_email, EmailNotValidError

from config.settings import settings

logger = logging.getLogger(__name__)

class EmailDeliveryResult:
    """Result of email delivery attempt"""
    def __init__(
        self,
        success: bool,
        message_id: Optional[str] = None,
        error: Optional[str] = None,
        timestamp: Optional[datetime] = None
    ):
        self.success = success
        self.message_id = message_id
        self.error = error
        self.timestamp = timestamp or datetime.now()

class EmailSender:
    """
    Handles email delivery through multiple providers
    """

    def __init__(self):
        self.provider = settings.email_provider
        self.from_email = settings.from_email

        # Initialize provider
        if self.provider == "sendgrid" and SENDGRID_AVAILABLE:
            self.sg_client = sendgrid.SendGridAPIClient(api_key=settings.sendgrid_api_key)
        elif self.provider == "ses" and SES_AVAILABLE:
            # Initialize Amazon SES client
            self.ses_client = boto3.client(
                'ses',
                region_name=getattr(settings, 'aws_region', 'us-east-1'),
                aws_access_key_id=getattr(settings, 'aws_access_key_id', None),
                aws_secret_access_key=getattr(settings, 'aws_secret_access_key', None)
            )
        elif self.provider == "smtp":
            self.smtp_config = {
                "hostname": settings.smtp_host,
                "port": settings.smtp_port,
                "username": settings.smtp_user,
                "password": settings.smtp_password
            }
        else:
            logger.warning(f"Email provider {self.provider} not configured properly")

    async def send_email(
        self,
        to_email: str,
        subject: str,
        body: str,
        html_body: Optional[str] = None,
        from_name: Optional[str] = None,
        reply_to: Optional[str] = None,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
        attachments: Optional[List[Dict[str, Any]]] = None
    ) -> EmailDeliveryResult:
        """Send a single email"""

        # Validate email
        try:
            validated = validate_email(to_email)
            to_email = validated.email
        except EmailNotValidError as e:
            logger.error(f"Invalid email address {to_email}: {e}")
            return EmailDeliveryResult(success=False, error=str(e))

        # Route to appropriate sender
        if self.provider == "sendgrid" and SENDGRID_AVAILABLE:
            return await self._send_via_sendgrid(
                to_email, subject, body, html_body,
                from_name, reply_to, cc, bcc, attachments
            )
        elif self.provider == "ses" and SES_AVAILABLE:
            return await self._send_via_ses(
                to_email, subject, body, html_body,
                from_name, reply_to, cc, bcc
            )
        elif self.provider == "smtp":
            return await self._send_via_smtp(
                to_email, subject, body, html_body,
                from_name, reply_to, cc, bcc
            )
        else:
            return await self._mock_send(to_email, subject)

    async def _send_via_sendgrid(
        self,
        to_email: str,
        subject: str,
        body: str,
        html_body: Optional[str] = None,
        from_name: Optional[str] = None,
        reply_to: Optional[str] = None,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
        attachments: Optional[List[Dict[str, Any]]] = None
    ) -> EmailDeliveryResult:
        """Send email via SendGrid"""

        try:
            # Create message
            message = Mail(
                from_email=(self.from_email, from_name or "Stalker Engine"),
                to_emails=to_email,
                subject=subject,
                plain_text_content=body
            )

            if html_body:
                message.html_content = html_body

            if reply_to:
                message.reply_to = Email(reply_to)

            # Add CC/BCC
            if cc:
                for email in cc:
                    message.add_cc(Email(email))
            if bcc:
                for email in bcc:
                    message.add_bcc(Email(email))

            # Send
            response = self.sg_client.send(message)

            if response.status_code in [200, 201, 202]:
                return EmailDeliveryResult(
                    success=True,
                    message_id=response.headers.get('X-Message-Id')
                )
            else:
                return EmailDeliveryResult(
                    success=False,
                    error=f"SendGrid returned status {response.status_code}"
                )

        except Exception as e:
            logger.error(f"SendGrid send failed: {e}")
            return EmailDeliveryResult(success=False, error=str(e))

    async def _send_via_ses(
        self,
        to_email: str,
        subject: str,
        body: str,
        html_body: Optional[str] = None,
        from_name: Optional[str] = None,
        reply_to: Optional[str] = None,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None
    ) -> EmailDeliveryResult:
        """Send email via Amazon SES"""

        try:
            # Prepare email
            destination = {'ToAddresses': [to_email]}
            if cc:
                destination['CcAddresses'] = cc
            if bcc:
                destination['BccAddresses'] = bcc

            # Email content
            message = {
                'Subject': {'Data': subject},
                'Body': {}
            }

            if body:
                message['Body']['Text'] = {'Data': body}
            if html_body:
                message['Body']['Html'] = {'Data': html_body}

            # From address
            from_address = self.from_email
            if from_name:
                from_address = f"{from_name} <{self.from_email}>"

            # Send email
            kwargs = {
                'Source': from_address,
                'Destination': destination,
                'Message': message
            }

            if reply_to:
                kwargs['ReplyToAddresses'] = [reply_to]

            # Use asyncio to run the synchronous boto3 call
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.ses_client.send_email(**kwargs)
            )

            return EmailDeliveryResult(
                success=True,
                message_id=response['MessageId']
            )

        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = e.response['Error']['Message']
            logger.error(f"SES send failed: {error_code} - {error_message}")
            return EmailDeliveryResult(success=False, error=f"{error_code}: {error_message}")
        except Exception as e:
            logger.error(f"SES send failed: {e}")
            return EmailDeliveryResult(success=False, error=str(e))

    async def _send_via_smtp(
        self,
        to_email: str,
        subject: str,
        body: str,
        html_body: Optional[str] = None,
        from_name: Optional[str] = None,
        reply_to: Optional[str] = None,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None
    ) -> EmailDeliveryResult:
        """Send email via SMTP"""

        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['From'] = f"{from_name or 'Stalker'} <{self.from_email}>"
            msg['To'] = to_email
            msg['Subject'] = subject

            if reply_to:
                msg['Reply-To'] = reply_to

            if cc:
                msg['Cc'] = ', '.join(cc)

            # Add body
            msg.attach(MIMEText(body, 'plain'))
            if html_body:
                msg.attach(MIMEText(html_body, 'html'))

            # Recipients list
            recipients = [to_email]
            if cc:
                recipients.extend(cc)
            if bcc:
                recipients.extend(bcc)

            # Send via aiosmtplib
            response = await aiosmtplib.send(
                msg,
                hostname=self.smtp_config["hostname"],
                port=self.smtp_config["port"],
                username=self.smtp_config["username"],
                password=self.smtp_config["password"],
                start_tls=True
            )

            return EmailDeliveryResult(
                success=True,
                message_id=response[1]
            )

        except Exception as e:
            logger.error(f"SMTP send failed: {e}")
            return EmailDeliveryResult(success=False, error=str(e))

    async def _mock_send(self, to_email: str, subject: str) -> EmailDeliveryResult:
        """Mock send for development"""
        logger.info(f"[MOCK] Email would be sent to {to_email}: {subject}")

        # Simulate delay
        await asyncio.sleep(0.5)

        return EmailDeliveryResult(
            success=True,
            message_id=f"mock_{datetime.now().timestamp()}"
        )

    async def send_bulk(
        self,
        recipients: List[Dict[str, Any]],
        template: Dict[str, str],
        batch_size: int = 10,
        delay_seconds: int = 1
    ) -> List[EmailDeliveryResult]:
        """
        Send emails in bulk with rate limiting

        recipients: List of dicts with {email, name, custom_vars}
        template: Dict with {subject, body, html_body}
        """

        results = []

        for i in range(0, len(recipients), batch_size):
            batch = recipients[i:i + batch_size]

            # Send batch in parallel
            tasks = []
            for recipient in batch:
                # Personalize template
                personalized_subject = self._personalize_text(
                    template["subject"], recipient.get("custom_vars", {})
                )
                personalized_body = self._personalize_text(
                    template["body"], recipient.get("custom_vars", {})
                )

                task = self.send_email(
                    to_email=recipient["email"],
                    subject=personalized_subject,
                    body=personalized_body,
                    html_body=template.get("html_body"),
                    from_name=template.get("from_name")
                )
                tasks.append(task)

            # Wait for batch to complete
            batch_results = await asyncio.gather(*tasks)
            results.extend(batch_results)

            # Rate limiting delay
            if i + batch_size < len(recipients):
                await asyncio.sleep(delay_seconds)

            # Log progress
            logger.info(f"Sent batch {i // batch_size + 1}/{len(recipients) // batch_size + 1}")

        return results

    def _personalize_text(self, text: str, variables: Dict[str, Any]) -> str:
        """Replace variables in text"""
        for key, value in variables.items():
            text = text.replace(f"{{{key}}}", str(value))
            text = text.replace(f"{{{{{key}}}}}", str(value))  # Double brackets
        return text

    async def verify_configuration(self) -> bool:
        """Verify email configuration is working"""
        try:
            if self.provider == "sendgrid" and SENDGRID_AVAILABLE:
                # Test SendGrid API key
                response = self.sg_client.client.api_keys._(settings.sendgrid_api_key).get()
                return response.status_code == 200

            elif self.provider == "ses" and SES_AVAILABLE:
                # Test SES configuration by getting send quota
                try:
                    loop = asyncio.get_event_loop()
                    response = await loop.run_in_executor(
                        None,
                        self.ses_client.get_send_quota
                    )
                    logger.info(f"SES Send Quota: {response}")
                    return True
                except ClientError as e:
                    logger.error(f"SES verification failed: {e}")
                    return False

            elif self.provider == "smtp":
                # Test SMTP connection
                async with aiosmtplib.SMTP(
                    hostname=self.smtp_config["hostname"],
                    port=self.smtp_config["port"],
                    start_tls=True
                ) as smtp:
                    await smtp.login(
                        self.smtp_config["username"],
                        self.smtp_config["password"]
                    )
                return True

            else:
                # Mock provider always works
                return True

        except Exception as e:
            logger.error(f"Email configuration verification failed: {e}")
            return False

class EmailTracker:
    """Track email metrics"""

    def __init__(self):
        self.sent_count = 0
        self.failed_count = 0
        self.bounce_count = 0
        self.open_count = 0
        self.click_count = 0
        self.reply_count = 0

    def record_sent(self, result: EmailDeliveryResult):
        """Record a send attempt"""
        if result.success:
            self.sent_count += 1
        else:
            self.failed_count += 1

    def get_metrics(self) -> Dict[str, Any]:
        """Get current metrics"""
        total_attempts = self.sent_count + self.failed_count
        return {
            "sent": self.sent_count,
            "failed": self.failed_count,
            "bounced": self.bounce_count,
            "opened": self.open_count,
            "clicked": self.click_count,
            "replied": self.reply_count,
            "success_rate": (self.sent_count / total_attempts * 100) if total_attempts > 0 else 0,
            "open_rate": (self.open_count / self.sent_count * 100) if self.sent_count > 0 else 0,
            "click_rate": (self.click_count / self.open_count * 100) if self.open_count > 0 else 0,
            "reply_rate": (self.reply_count / self.sent_count * 100) if self.sent_count > 0 else 0
        }