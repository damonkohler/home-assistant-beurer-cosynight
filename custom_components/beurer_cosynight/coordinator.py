"""DataUpdateCoordinator for Beurer CosyNight integration."""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .beurer_cosynight import ApiError, AuthError, BeurerCosyNight, Quickstart, Status

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
        self.quickstart_lock = asyncio.Lock()

    async def execute_quickstart(self, quickstart: Quickstart) -> None:
        """Execute a quickstart command with lock, error handling, and state update.

        Acquires the quickstart lock, sends the command to the API,
        maps API errors to HomeAssistantError, and updates the
        coordinator data from the response.

        Callers that need to read coordinator data atomically with the
        API call (e.g. zone entities reading the other zone's current
        value) should use ``execute_quickstart_unlocked`` inside their
        own ``async with self.quickstart_lock`` block instead.

        Args:
            quickstart: The quickstart command to send.

        Raises:
            HomeAssistantError: On authentication or API failure.
        """
        async with self.quickstart_lock:
            await self.execute_quickstart_unlocked(quickstart)

    async def execute_quickstart_unlocked(self, quickstart: Quickstart) -> None:
        """Execute a quickstart command without acquiring the lock.

        The caller must hold ``quickstart_lock`` before calling this
        method. Use ``execute_quickstart`` for the common case where
        the lock is not already held.

        Args:
            quickstart: The quickstart command to send.

        Raises:
            HomeAssistantError: On authentication or API failure.
        """
        try:
            status = await self.hub.quickstart(quickstart)
        except AuthError as err:
            raise HomeAssistantError("Authentication failed") from err
        except ApiError as err:
            raise HomeAssistantError(f"API error: {err}") from err
        self.async_set_updated_data(status)

    async def _async_update_data(self) -> Status:
        """Fetch device status from API."""
        try:
            return await self.hub.get_status(self.device_id)
        except AuthError as err:
            raise ConfigEntryAuthFailed("Authentication failed during polling") from err
        except ApiError as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err
