"""Tests for EndpointValidationService debounce logic."""

import time
from unittest.mock import patch

import pytest

from rhesis.backend.app.services.connector.mapping.endpoint_validator import (
    _DEBOUNCE_SECONDS,
    EndpointValidationService,
)


@pytest.fixture
def service():
    return EndpointValidationService()


class TestValidationDebounce:
    @pytest.mark.asyncio
    async def test_first_call_runs_validation(self, service):
        with patch.object(service, "_track_background_task") as mock_track:
            await service.start_validation("proj", "dev", [{"name": "fn"}], "org-1", "user-1")
            mock_track.assert_called_once()

    @pytest.mark.asyncio
    async def test_rapid_second_call_is_debounced(self, service):
        with patch.object(service, "_track_background_task") as mock_track:
            await service.start_validation("proj", "dev", [{"name": "fn"}], "org-1", "user-1")
            await service.start_validation("proj", "dev", [{"name": "fn"}], "org-1", "user-1")
            assert mock_track.call_count == 1

    @pytest.mark.asyncio
    async def test_different_keys_are_independent(self, service):
        with patch.object(service, "_track_background_task") as mock_track:
            await service.start_validation("proj", "dev", [{"name": "fn"}], "org-1", "user-1")
            await service.start_validation("proj", "staging", [{"name": "fn"}], "org-1", "user-1")
            assert mock_track.call_count == 2

    @pytest.mark.asyncio
    async def test_runs_again_after_debounce_window(self, service):
        with patch.object(service, "_track_background_task") as mock_track:
            await service.start_validation("proj", "dev", [{"name": "fn"}], "org-1", "user-1")
            service._last_validation["proj:dev"] = time.monotonic() - _DEBOUNCE_SECONDS - 1
            await service.start_validation("proj", "dev", [{"name": "fn"}], "org-1", "user-1")
            assert mock_track.call_count == 2
