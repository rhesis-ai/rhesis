"""
Tests for Day 1/2/3 onboarding email scheduling via SendGrid.

These tests guard against silent failures — the primary risk identified in the
email architecture review: missing env vars causing emails to be quietly dropped
with no indication in the HTTP response.
"""

from unittest.mock import MagicMock, patch

import pytest

from rhesis.backend.notifications.email.sendgrid_client import SendGridClient
from rhesis.backend.notifications.email.service import EmailService

# ---------------------------------------------------------------------------
# SendGridClient unit tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestSendGridClientConfiguration:
    """SendGridClient must clearly report misconfiguration."""

    def test_is_not_configured_when_api_key_missing(self):
        with patch.dict("os.environ", {}, clear=True):
            # Ensure the key is definitely absent
            import os

            os.environ.pop("SENDGRID_API_KEY", None)
            client = SendGridClient()
            assert not client.is_configured

    def test_is_configured_when_api_key_present(self):
        with patch.dict("os.environ", {"SENDGRID_API_KEY": "SG.test-key"}):
            client = SendGridClient()
            assert client.is_configured

    def test_returns_false_when_api_key_missing(self):
        """Missing API key must return False, not raise an exception."""
        with patch.dict("os.environ", {}, clear=True):
            import os

            os.environ.pop("SENDGRID_API_KEY", None)
            client = SendGridClient()
            result = client.send_scheduled_dynamic_template(
                template_id="d-abc123",
                recipient_email="user@example.com",
                recipient_name="Test User",
                subject="Day 1 with Rhesis AI",
                from_email="hello@rhesis.ai",
                dynamic_template_data={"recipient_name": "Test User"},
                delay_hours=23,
                delay_minutes=59,
            )
            assert result is False

    def test_simulate_mode_skips_api_call_and_returns_true(self):
        """Simulate=True must log the payload and return True without calling SendGrid."""
        with patch.dict("os.environ", {"SENDGRID_API_KEY": "SG.test-key"}):
            client = SendGridClient()
            with patch.object(client, "api_key", "SG.test-key"):
                # Patch the SendGridAPIClient so no real network call is made
                with patch(
                    "rhesis.backend.notifications.email.sendgrid_client.SendGridAPIClient"
                ) as mock_sg:
                    result = client.send_scheduled_dynamic_template(
                        template_id="d-abc123",
                        recipient_email="user@example.com",
                        recipient_name="Test User",
                        subject="Day 1 with Rhesis AI",
                        from_email="hello@rhesis.ai",
                        dynamic_template_data={"recipient_name": "Test User"},
                        delay_hours=0,
                        delay_minutes=1,
                        simulate=True,
                    )
                    # Should succeed without touching the real API
                    assert result is True
                    mock_sg.assert_not_called()

    def test_real_send_calls_sendgrid_api(self):
        """When fully configured and simulate=False, the SendGrid client is called."""
        with patch.dict("os.environ", {"SENDGRID_API_KEY": "SG.test-key"}):
            client = SendGridClient()
            mock_response = MagicMock()
            mock_response.status_code = 202

            with patch(
                "rhesis.backend.notifications.email.sendgrid_client.SendGridAPIClient"
            ) as mock_sg_class:
                mock_sg_instance = MagicMock()
                mock_sg_instance.send.return_value = mock_response
                mock_sg_class.return_value = mock_sg_instance

                result = client.send_scheduled_dynamic_template(
                    template_id="d-abc123",
                    recipient_email="user@example.com",
                    recipient_name="Test User",
                    subject="Day 1 with Rhesis AI",
                    from_email="hello@rhesis.ai",
                    dynamic_template_data={"recipient_name": "Test User"},
                    delay_hours=23,
                    delay_minutes=59,
                    simulate=False,
                )

                assert result is True
                mock_sg_instance.send.assert_called_once()

    def test_returns_false_on_sendgrid_error_status(self):
        """Non-2xx SendGrid response must return False."""
        with patch.dict("os.environ", {"SENDGRID_API_KEY": "SG.test-key"}):
            client = SendGridClient()
            mock_response = MagicMock()
            mock_response.status_code = 400
            mock_response.body = b"Bad Request"

            with patch(
                "rhesis.backend.notifications.email.sendgrid_client.SendGridAPIClient"
            ) as mock_sg_class:
                mock_sg_instance = MagicMock()
                mock_sg_instance.send.return_value = mock_response
                mock_sg_class.return_value = mock_sg_instance

                result = client.send_scheduled_dynamic_template(
                    template_id="d-abc123",
                    recipient_email="user@example.com",
                    recipient_name="Test User",
                    subject="Day 1 with Rhesis AI",
                    from_email="hello@rhesis.ai",
                    dynamic_template_data={"recipient_name": "Test User"},
                    delay_hours=23,
                    delay_minutes=59,
                )
                assert result is False

    def test_returns_false_on_exception(self):
        """Network/API exceptions must be caught and return False, not propagate."""
        with patch.dict("os.environ", {"SENDGRID_API_KEY": "SG.test-key"}):
            client = SendGridClient()

            with patch(
                "rhesis.backend.notifications.email.sendgrid_client.SendGridAPIClient"
            ) as mock_sg_class:
                mock_sg_class.side_effect = Exception("Network error")

                result = client.send_scheduled_dynamic_template(
                    template_id="d-abc123",
                    recipient_email="user@example.com",
                    recipient_name="Test User",
                    subject="Day 1 with Rhesis AI",
                    from_email="hello@rhesis.ai",
                    dynamic_template_data={"recipient_name": "Test User"},
                    delay_hours=23,
                    delay_minutes=59,
                )
                assert result is False


# ---------------------------------------------------------------------------
# EmailService unit tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestOnboardingEmailService:
    """EmailService.send_day_X_email must handle all failure cases explicitly."""

    def _make_service_with_mock_client(self, is_configured=True):
        """Create an EmailService with a mocked SendGridClient."""
        service = EmailService.__new__(EmailService)
        mock_sg = MagicMock(spec=SendGridClient)
        mock_sg.is_configured = is_configured
        service.sendgrid_client = mock_sg
        service.smtp_service = MagicMock()
        service.template_service = MagicMock()
        return service, mock_sg

    def test_send_day_1_returns_false_when_api_key_missing(self):
        service, mock_sg = self._make_service_with_mock_client(is_configured=False)
        result = service.send_day_1_email(
            recipient_email="user@example.com",
            recipient_name="Test User",
        )
        assert result is False
        mock_sg.send_scheduled_dynamic_template.assert_not_called()

    def test_send_day_2_returns_false_when_api_key_missing(self):
        service, mock_sg = self._make_service_with_mock_client(is_configured=False)
        result = service.send_day_2_email(
            recipient_email="user@example.com",
            recipient_name="Test User",
        )
        assert result is False

    def test_send_day_3_returns_false_when_api_key_missing(self):
        service, mock_sg = self._make_service_with_mock_client(is_configured=False)
        result = service.send_day_3_email(
            recipient_email="user@example.com",
            recipient_name="Test User",
        )
        assert result is False

    def test_send_day_1_returns_false_when_template_id_missing(self):
        """Missing template ID env var must return False, not raise."""
        service, mock_sg = self._make_service_with_mock_client(is_configured=True)
        env = {"SENDGRID_API_KEY": "SG.test-key"}
        # Deliberately omit SENDGRID_DAY_1_EMAIL_TEMPLATE_ID
        with patch.dict("os.environ", env, clear=False):
            import os

            os.environ.pop("SENDGRID_DAY_1_EMAIL_TEMPLATE_ID", None)
            result = service.send_day_1_email(
                recipient_email="user@example.com",
                recipient_name="Test User",
            )
        assert result is False
        mock_sg.send_scheduled_dynamic_template.assert_not_called()

    def test_send_day_2_returns_false_when_template_id_missing(self):
        service, mock_sg = self._make_service_with_mock_client(is_configured=True)
        with patch.dict("os.environ", {"SENDGRID_API_KEY": "SG.test-key"}, clear=False):
            import os

            os.environ.pop("SENDGRID_DAY_2_EMAIL_TEMPLATE_ID", None)
            result = service.send_day_2_email(
                recipient_email="user@example.com",
                recipient_name="Test User",
            )
        assert result is False

    def test_send_day_3_returns_false_when_template_id_missing(self):
        service, mock_sg = self._make_service_with_mock_client(is_configured=True)
        with patch.dict("os.environ", {"SENDGRID_API_KEY": "SG.test-key"}, clear=False):
            import os

            os.environ.pop("SENDGRID_DAY_3_EMAIL_TEMPLATE_ID", None)
            result = service.send_day_3_email(
                recipient_email="user@example.com",
                recipient_name="Test User",
            )
        assert result is False

    def test_send_day_1_schedules_with_correct_delay(self):
        """Day 1 must be scheduled for 23h 59m."""
        service, mock_sg = self._make_service_with_mock_client(is_configured=True)
        mock_sg.send_scheduled_dynamic_template.return_value = True
        env = {
            "SENDGRID_API_KEY": "SG.test-key",
            "SENDGRID_DAY_1_EMAIL_TEMPLATE_ID": "d-day1-template",
        }
        with patch.dict("os.environ", env):
            service.send_day_1_email(
                recipient_email="user@example.com",
                recipient_name="Test User",
            )
        call_kwargs = mock_sg.send_scheduled_dynamic_template.call_args.kwargs
        assert call_kwargs["delay_hours"] == 23
        assert call_kwargs["delay_minutes"] == 59

    def test_send_day_2_schedules_with_correct_delay(self):
        """Day 2 must be scheduled for 48h."""
        service, mock_sg = self._make_service_with_mock_client(is_configured=True)
        mock_sg.send_scheduled_dynamic_template.return_value = True
        env = {
            "SENDGRID_API_KEY": "SG.test-key",
            "SENDGRID_DAY_2_EMAIL_TEMPLATE_ID": "d-day2-template",
        }
        with patch.dict("os.environ", env):
            service.send_day_2_email(
                recipient_email="user@example.com",
                recipient_name="Test User",
            )
        call_kwargs = mock_sg.send_scheduled_dynamic_template.call_args.kwargs
        assert call_kwargs["delay_hours"] == 48

    def test_send_day_3_schedules_within_sendgrid_72h_limit(self):
        """Day 3 must be scheduled strictly below SendGrid's 72-hour max."""
        service, mock_sg = self._make_service_with_mock_client(is_configured=True)
        mock_sg.send_scheduled_dynamic_template.return_value = True
        env = {
            "SENDGRID_API_KEY": "SG.test-key",
            "SENDGRID_DAY_3_EMAIL_TEMPLATE_ID": "d-day3-template",
        }
        with patch.dict("os.environ", env):
            service.send_day_3_email(
                recipient_email="user@example.com",
                recipient_name="Test User",
            )
        call_kwargs = mock_sg.send_scheduled_dynamic_template.call_args.kwargs
        total_minutes = call_kwargs["delay_hours"] * 60 + call_kwargs.get("delay_minutes", 0)
        assert total_minutes < 72 * 60, (
            f"Day 3 delay ({total_minutes} min) must be < 72 hours (4320 min) "
            "to stay within SendGrid's scheduling limit"
        )

    def test_send_day_1_passes_correct_template_id(self):
        """The template ID read from the env var must be forwarded to the client."""
        service, mock_sg = self._make_service_with_mock_client(is_configured=True)
        mock_sg.send_scheduled_dynamic_template.return_value = True
        env = {
            "SENDGRID_API_KEY": "SG.test-key",
            "SENDGRID_DAY_1_EMAIL_TEMPLATE_ID": "d-correct-day1-id",
        }
        with patch.dict("os.environ", env):
            service.send_day_1_email(
                recipient_email="user@example.com",
                recipient_name="Test User",
            )
        call_kwargs = mock_sg.send_scheduled_dynamic_template.call_args.kwargs
        assert call_kwargs["template_id"] == "d-correct-day1-id"

    def test_all_three_days_use_different_template_ids(self):
        """Each day must read its own template ID env var."""
        service, mock_sg = self._make_service_with_mock_client(is_configured=True)
        mock_sg.send_scheduled_dynamic_template.return_value = True
        env = {
            "SENDGRID_API_KEY": "SG.test-key",
            "SENDGRID_DAY_1_EMAIL_TEMPLATE_ID": "d-day1",
            "SENDGRID_DAY_2_EMAIL_TEMPLATE_ID": "d-day2",
            "SENDGRID_DAY_3_EMAIL_TEMPLATE_ID": "d-day3",
        }
        used_template_ids = []
        with patch.dict("os.environ", env):
            service.send_day_1_email("u@e.com", "User")
            used_template_ids.append(
                mock_sg.send_scheduled_dynamic_template.call_args.kwargs["template_id"]
            )
            service.send_day_2_email("u@e.com", "User")
            used_template_ids.append(
                mock_sg.send_scheduled_dynamic_template.call_args.kwargs["template_id"]
            )
            service.send_day_3_email("u@e.com", "User")
            used_template_ids.append(
                mock_sg.send_scheduled_dynamic_template.call_args.kwargs["template_id"]
            )

        assert used_template_ids == ["d-day1", "d-day2", "d-day3"], (
            f"Each day must use its own template ID — got: {used_template_ids}"
        )
