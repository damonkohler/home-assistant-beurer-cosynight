"""Shared fixtures for Beurer CosyNight tests."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.beurer_cosynight.beurer_cosynight import (
    BeurerCosyNight,
    Device,
    Status,
)
from custom_components.beurer_cosynight.const import DOMAIN

MOCK_USERNAME = "test@example.com"
MOCK_PASSWORD = "testpass123"
MOCK_DEVICE_ID = "device-abc-123"
MOCK_DEVICE_NAME = "My Mattress Pad"
MOCK_ENTRY_ID = "test_entry_id_123"


@pytest.fixture
def mock_device() -> Device:
    """Return a mock Device."""
    return Device(
        active=True,
        id=MOCK_DEVICE_ID,
        name=MOCK_DEVICE_NAME,
        requiresUpdate=False,
    )


@pytest.fixture
def mock_status() -> Status:
    """Return a mock Status."""
    return Status(
        active=True,
        bodySetting=3,
        feetSetting=5,
        heartbeat=100,
        id=MOCK_DEVICE_ID,
        name=MOCK_DEVICE_NAME,
        requiresUpdate=False,
        timer=1800,
    )


@pytest.fixture
def mock_hub(mock_device, mock_status) -> MagicMock:
    """Return a mock BeurerCosyNight hub."""
    hub = MagicMock(spec=BeurerCosyNight)
    hub.authenticate.return_value = None
    hub.list_devices.return_value = [mock_device]
    hub.get_status.return_value = mock_status
    hub.quickstart.return_value = None
    return hub


@pytest.fixture
def mock_hass(tmp_path):
    """Return a lightweight mock HomeAssistant."""
    hass = MagicMock()
    hass.config.path.return_value = str(tmp_path / ".storage" / "beurer_token")
    hass.data = {}

    # async_add_executor_job: run the function synchronously in tests
    async def _executor_job(func, *args):
        return func(*args)

    hass.async_add_executor_job = _executor_job
    return hass
