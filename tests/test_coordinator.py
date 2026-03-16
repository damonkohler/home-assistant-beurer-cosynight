"""Tests for the Beurer CosyNight DataUpdateCoordinator."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.beurer_cosynight.beurer_cosynight import (
    ApiError,
    AuthError,
    BeurerCosyNight,
)
from custom_components.beurer_cosynight.coordinator import (
    BeurerCosyNightCoordinator,
    UPDATE_INTERVAL,
)

from .conftest import MOCK_DEVICE_ID


class TestCoordinatorWiring:
    """Test coordinator correctly delegates to hub."""

    def test_update_interval_is_30_seconds(self):
        """Coordinator should poll every 30 seconds."""
        assert UPDATE_INTERVAL.total_seconds() == 30

    @pytest.mark.asyncio
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

    @pytest.mark.asyncio
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

    @pytest.mark.asyncio
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
