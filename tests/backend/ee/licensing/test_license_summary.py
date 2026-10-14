"""The licence line each process logs at startup, so a worker started without
``RHESIS_LICENSE`` shows it rather than failing licensed jobs silently."""

import logging
import time
from unittest.mock import patch

import pytest

import rhesis.backend.ee as ee

LOGGER = "rhesis.backend.ee"


@pytest.fixture(autouse=True)
def fresh_process():
    ee._license_logged = False
    yield
    ee._license_logged = False


def _summary(caplog, token: str) -> list[logging.LogRecord]:
    with caplog.at_level(logging.INFO, logger=LOGGER):
        with patch.dict("os.environ", {"RHESIS_LICENSE": token}):
            ee.log_license_summary()
    return [r for r in caplog.records if r.name == LOGGER]


def test_blanket_licence(caplog, mint_token):
    [record] = _summary(caplog, mint_token(sub="*"))
    assert record.levelno == logging.INFO
    assert "enterprise edition, active, for all organizations" in record.getMessage()


def test_org_licence_names_the_org(caplog, mint_token):
    [record] = _summary(caplog, mint_token(sub="00000000-0000-0000-0000-000000000001"))
    assert "for 00000000-0000-0000-0000-000000000001" in record.getMessage()


def test_no_licence_is_info_not_a_warning(caplog):
    [record] = _summary(caplog, "")
    assert record.levelno == logging.INFO
    assert "No RHESIS_LICENSE set" in record.getMessage()


def test_expired_licence_warns(caplog, mint_token):
    [record] = _summary(caplog, mint_token(sub="*", exp=int(time.time()) - 3600))
    assert record.levelno == logging.WARNING
    assert "invalid or expired" in record.getMessage()


def test_logs_once_per_process(caplog, mint_token):
    token = mint_token(sub="*")
    _summary(caplog, token)
    assert len(_summary(caplog, token)) == 1
