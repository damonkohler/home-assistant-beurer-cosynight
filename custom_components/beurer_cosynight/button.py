"""Button entities for Beurer CosyNight integration."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import beurer_cosynight
from .const import DOMAIN
from .coordinator import BeurerCosyNightCoordinator


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
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.id)},
            name=device.name,
            manufacturer="Beurer",
            model="CosyNight",
        )

    async def async_press(self) -> None:
        """Stop the heating session by setting both zones to 0."""
        qs = beurer_cosynight.Quickstart(
            bodySetting=0,
            feetSetting=0,
            id=self._device.id,
            timespan=0,
        )
        await self.hass.async_add_executor_job(self.coordinator.hub.quickstart, qs)
        await self.coordinator.async_request_refresh()
