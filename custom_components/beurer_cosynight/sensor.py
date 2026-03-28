"""Sensor entities for Beurer CosyNight integration."""

from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
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
    """Set up Beurer CosyNight sensor entities from a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    devices: list[beurer_cosynight.Device] = data["devices"]
    coordinators: dict[str, BeurerCosyNightCoordinator] = data["coordinators"]

    async_add_entities(
        [DeviceTimerSensor(coordinators[d.id], d) for d in devices],
    )


class DeviceTimerSensor(CoordinatorEntity[BeurerCosyNightCoordinator], SensorEntity):
    """Sensor showing remaining session time on the device."""

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    _attr_icon = "mdi:timer-sand"

    def __init__(
        self,
        coordinator: BeurerCosyNightCoordinator,
        device: beurer_cosynight.Device,
    ) -> None:
        super().__init__(coordinator)
        self._attr_name = "Remaining Time"
        self._attr_unique_id = f"beurer_cosynight_{device.id}_remaining_time"
        self._attr_device_info = device_info_for(device)

    @property
    def native_value(self) -> int | None:
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.timer
