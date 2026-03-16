"""DataUpdateCoordinator for Beurer CosyNight integration."""

from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .beurer_cosynight import AuthError, ApiError, BeurerCosyNight, Status

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = timedelta(seconds=30)


class BeurerCosyNightCoordinator(DataUpdateCoordinator[Status]):
    """Coordinator to fetch device status from Beurer CosyNight API."""

    def __init__(
        self,
        hass: HomeAssistant,
        hub: BeurerCosyNight,
        device_id: str,
        device_name: str,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"Beurer CosyNight {device_name}",
            update_interval=UPDATE_INTERVAL,
        )
        self.hub = hub
        self.device_id = device_id

    async def _async_update_data(self) -> Status:
        """Fetch device status from API."""
        try:
            return await self.hub.get_status(self.device_id)
        except AuthError as err:
            raise ConfigEntryAuthFailed("Authentication failed during polling") from err
        except ApiError as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err
