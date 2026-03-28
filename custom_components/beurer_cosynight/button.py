"""Button entities for Beurer CosyNight integration."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import beurer_cosynight
from .const import DOMAIN
from .coordinator import BeurerCosyNightCoordinator
from .helpers import device_info_for


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Beurer CosyNight button entities from a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    devices: list[beurer_cosynight.Device] = data["devices"]
    coordinators: dict[str, BeurerCosyNightCoordinator] = data["coordinators"]

    async_add_entities([StopButton(coordinators[d.id], d) for d in devices])


class StopButton(CoordinatorEntity[BeurerCosyNightCoordinator], ButtonEntity):
    """Button to stop an active heating session."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:stop-circle-outline"

    def __init__(
        self,
        coordinator: BeurerCosyNightCoordinator,
        device: beurer_cosynight.Device,
    ) -> None:
        super().__init__(coordinator)
        self._device = device
        self._attr_name = "Stop"
        self._attr_unique_id = f"beurer_cosynight_{device.id}_stop"
        self._attr_device_info = device_info_for(device)

    async def async_press(self) -> None:
        """Stop the heating session by setting both zones to 0."""
        async with self.coordinator.quickstart_lock:
            qs = beurer_cosynight.Quickstart(
                bodySetting=0,
                feetSetting=0,
                id=self._device.id,
                timespan=0,
            )
            try:
                status = await self.coordinator.hub.quickstart(qs)
            except beurer_cosynight.AuthError as err:
                raise HomeAssistantError("Authentication failed") from err
            except beurer_cosynight.ApiError as err:
                raise HomeAssistantError(f"API error: {err}") from err
            self.coordinator.async_set_updated_data(status)
