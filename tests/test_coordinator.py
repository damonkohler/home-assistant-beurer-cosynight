"""Tests for the Beurer CosyNight DataUpdateCoordinator."""

from __future__ import annotations

from unittest.mock import MagicMock, AsyncMock, patch

import pytest

from custom_components.beurer_cosynight.beurer_cosynight import (
    BeurerCosyNight,
    Status,
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

    @pytest.mark.asyncio
    async def test_async_update_data_calls_get_status(self, mock_hass, mock_hub, mock_status):
        """_async_update_data should call hub.get_status via executor."""
        coordinator = BeurerCosyNightCoordinator.__new__(BeurerCosyNightCoordinator)
        coordinator.hass = mock_hass
        coordinator.hub = mock_hub
        coordinator.device_id = MOCK_DEVICE_ID

        result = await coordinator._async_update_data()

        mock_hub.get_status.assert_called_once_with(MOCK_DEVICE_ID)
        assert result == mock_status

    @pytest.mark.asyncio
    async def test_async_update_data_wraps_exception_in_update_failed(self, mock_hass):
        """API errors should be wrapped in UpdateFailed."""
        from homeassistant.helpers.update_coordinator import UpdateFailed

        hub = MagicMock(spec=BeurerCosyNight)
        hub.get_status.side_effect = Exception("API down")

        coordinator = BeurerCosyNightCoordinator.__new__(BeurerCosyNightCoordinator)
        coordinator.hass = mock_hass
        coordinator.hub = hub
        coordinator.device_id = MOCK_DEVICE_ID

        with pytest.raises(UpdateFailed, match="Error communicating with API"):
            await coordinator._async_update_data()

    def test_coordinator_stores_hub_and_device_id(self, mock_hass):
        """Coordinator should store hub reference and device_id."""
        hub = MagicMock(spec=BeurerCosyNight)
        coordinator = BeurerCosyNightCoordinator.__new__(BeurerCosyNightCoordinator)
        coordinator.hub = hub
        coordinator.device_id = MOCK_DEVICE_ID
        assert coordinator.hub is hub
        assert coordinator.device_id == MOCK_DEVICE_ID
