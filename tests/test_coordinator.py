"""Tests for the Beurer CosyNight DataUpdateCoordinator."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from custom_components.beurer_cosynight.beurer_cosynight import (
    ApiError,
    AuthError,
    BeurerCosyNight,
)
from custom_components.beurer_cosynight.coordinator import (
    BeurerCosyNightCoordinator,
    UPDATE_INTERVAL,
)

from .conftest import MOCK_DEVICE_ID, MOCK_DEVICE_NAME


class TestCoordinatorWiring:
    """Test coordinator correctly delegates to hub."""

    def test_update_interval_is_30_seconds(self):
        """Coordinator should poll every 30 seconds."""
        assert UPDATE_INTERVAL.total_seconds() == 30

    async def test_async_update_data_calls_get_status(self, mock_hass, mock_status):
        """_async_update_data should await hub.get_status directly."""
        hub = AsyncMock(spec=BeurerCosyNight)
        hub.get_status.return_value = mock_status

        coordinator = BeurerCosyNightCoordinator.__new__(BeurerCosyNightCoordinator)
        coordinator.hass = mock_hass
        coordinator.hub = hub
        coordinator.device_id = MOCK_DEVICE_ID

        result = await coordinator._async_update_data()

        hub.get_status.assert_awaited_once_with(MOCK_DEVICE_ID)
        assert result == mock_status

    async def test_auth_error_raises_config_entry_auth_failed(self, mock_hass):
        """AuthError from hub should raise ConfigEntryAuthFailed."""
        hub = AsyncMock(spec=BeurerCosyNight)
        hub.get_status.side_effect = AuthError("token expired")

        coordinator = BeurerCosyNightCoordinator.__new__(BeurerCosyNightCoordinator)
        coordinator.hass = mock_hass
        coordinator.hub = hub
        coordinator.device_id = MOCK_DEVICE_ID

        with pytest.raises(ConfigEntryAuthFailed):
            await coordinator._async_update_data()

    async def test_api_error_raises_update_failed(self, mock_hass):
        """ApiError from hub should raise UpdateFailed."""
        hub = AsyncMock(spec=BeurerCosyNight)
        hub.get_status.side_effect = ApiError("server error")

        coordinator = BeurerCosyNightCoordinator.__new__(BeurerCosyNightCoordinator)
        coordinator.hass = mock_hass
        coordinator.hub = hub
        coordinator.device_id = MOCK_DEVICE_ID

        with pytest.raises(UpdateFailed):
            await coordinator._async_update_data()

    def test_coordinator_stores_hub_and_device_id(self, mock_hass):
        """Coordinator should store hub reference and device_id."""
        hub = AsyncMock(spec=BeurerCosyNight)
        coordinator = BeurerCosyNightCoordinator.__new__(BeurerCosyNightCoordinator)
        coordinator.hub = hub
        coordinator.device_id = MOCK_DEVICE_ID
        assert coordinator.hub is hub
        assert coordinator.device_id == MOCK_DEVICE_ID


class TestQuickstartLock:
    """Test quickstart_lock on the coordinator.

    We patch DataUpdateCoordinator.__init__ to a no-op so we can call the
    real BeurerCosyNightCoordinator.__init__ without needing a fully
    initialized HA runtime.
    """

    def test_quickstart_lock_is_asyncio_lock(self, mock_hass):
        """Coordinator __init__ should create an asyncio.Lock for quickstart_lock."""
        hub = AsyncMock(spec=BeurerCosyNight)
        with patch.object(DataUpdateCoordinator, "__init__", return_value=None):
            coord = BeurerCosyNightCoordinator(
                mock_hass, hub, MOCK_DEVICE_ID, MOCK_DEVICE_NAME
            )
        assert isinstance(coord.quickstart_lock, asyncio.Lock)

    def test_quickstart_lock_is_not_shared_between_coordinators(self, mock_hass):
        """Each coordinator instance should have its own lock."""
        hub = AsyncMock(spec=BeurerCosyNight)
        with patch.object(DataUpdateCoordinator, "__init__", return_value=None):
            coord_a = BeurerCosyNightCoordinator(mock_hass, hub, "dev-a", "A")
            coord_b = BeurerCosyNightCoordinator(mock_hass, hub, "dev-b", "B")
        assert coord_a.quickstart_lock is not coord_b.quickstart_lock
