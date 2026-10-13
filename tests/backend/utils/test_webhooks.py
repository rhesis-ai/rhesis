"""Signed outbound webhooks: ``app/utils/webhooks.py``.

Run with:
    cd apps/backend
    uv run pytest ../../tests/backend/utils/test_webhooks.py -v
"""

import base64

import pytest

from rhesis.backend.app.utils import webhooks
from rhesis.backend.app.utils.ssrf_http_client import SSRFError
from tests.backend.utils.webhook_receiver import fake_receiver

URL = "https://hooks.example.com/rhesis"


class TestSigning:
    def test_matches_the_standard_webhooks_reference_vector(self):
        # From the Standard Webhooks spec's reference libraries.
        signature = webhooks.sign(
            "whsec_MfKQ9r8GKYqrTwjUPD8ILPZIo2LaLaSw",
            "msg_p5jXN8AQM9LWM0D4loKWxJek",
            1614265330,
            b'{"test": 2432232314}',
        )
        assert signature == "v1,g0hM9SsE+OTPJTGt/tmIKtSyZlE3uFJELVlNIOLJ1OE="

    def test_headers_sign_the_body(self):
        secret = webhooks.generate_secret()
        headers = webhooks.signed_headers(secret, "msg_1", b"{}", timestamp=1700000000)
        assert headers["webhook-id"] == "msg_1"
        assert headers["webhook-timestamp"] == "1700000000"
        assert headers["webhook-signature"] == webhooks.sign(secret, "msg_1", 1700000000, b"{}")

    def test_generated_secret_is_24_random_bytes(self):
        secret = webhooks.generate_secret()
        assert secret.startswith("whsec_")
        assert len(base64.b64decode(secret.removeprefix("whsec_"))) == 24
        assert secret != webhooks.generate_secret()


class TestDestinationChecks:
    def test_public_https_is_accepted(self):
        with fake_receiver():
            webhooks.check_destination_url(URL)

    def test_http_is_refused(self):
        with fake_receiver(), pytest.raises(SSRFError, match="HTTPS"):
            webhooks.check_destination_url("http://hooks.example.com/rhesis")

    @pytest.mark.parametrize(
        "ip", ["10.0.0.5", "172.16.3.4", "192.168.1.1", "127.0.0.1", "169.254.169.254", "fe80::1"]
    )
    def test_names_resolving_to_internal_addresses_are_refused(self, ip):
        with fake_receiver(addresses={"hooks.example.com": ip}), pytest.raises(SSRFError):
            webhooks.check_destination_url(URL)

    def test_metadata_host_is_refused(self):
        with pytest.raises(SSRFError):
            webhooks.check_destination_url("https://metadata.google.internal/")


class TestPost:
    def test_sends_body_and_signed_headers(self):
        secret = webhooks.generate_secret()
        with fake_receiver() as received:
            response = webhooks.post_signed(URL, secret, "msg_1", b'{"a":1}')
        assert response.status_code == 200
        (request,) = received
        assert str(request.url) == URL
        assert request.content == b'{"a":1}'
        timestamp = int(request.headers["webhook-timestamp"])
        assert request.headers["webhook-signature"] == webhooks.sign(
            secret, "msg_1", timestamp, b'{"a":1}'
        )

    def test_does_not_follow_redirects(self):
        with fake_receiver(status=302, location="https://elsewhere.example.com/") as received:
            response = webhooks.post(URL, b"{}", {})
        assert response.status_code == 302
        assert len(received) == 1

    def test_address_is_checked_again_at_send_time(self):
        # A name that was public when saved and points inside now (DNS rebinding).
        with fake_receiver(addresses={"hooks.example.com": "10.0.0.5"}) as received:
            with pytest.raises(SSRFError):
                webhooks.post(URL, b"{}", {})
        assert received == []

    def test_refuses_http(self):
        with fake_receiver() as received, pytest.raises(SSRFError, match="HTTPS"):
            webhooks.post("http://hooks.example.com/", b"{}", {})
        assert received == []

    def test_has_a_timeout_and_verifies_tls(self):
        with fake_receiver() as received:
            webhooks.post(URL, b"{}", {})
        assert received.client_options == [
            {"timeout": webhooks.TIMEOUT_SECONDS, "verify": True, "follow_redirects": False}
        ]
