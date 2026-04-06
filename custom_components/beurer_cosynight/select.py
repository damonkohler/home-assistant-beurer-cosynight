"""Select entities for Beurer CosyNight integration."""

from __future__ import annotations

from abc import abstractmethod

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import beurer_cosynight
from .const import DOMAIN
from .coordinator import BeurerCosyNightCoordinator
from .helpers import device_info_for
from .number import TimerNumber


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Beurer CosyNight select entities from a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    devices: list[beurer_cosynight.Device] = data["devices"]
    coordinators: dict[str, BeurerCosyNightCoordinator] = data["coordinators"]

    timers: dict[str, TimerNumber] = data["timers"]

    entities: list[SelectEntity] = []
    for device in devices:
        coordinator = coordinators[device.id]
        timer = timers[device.id]
        entities.append(BodyZone(coordinator, device, timer))
        entities.append(FeetZone(coordinator, device, timer))
    async_add_entities(entities)


class _Zone(CoordinatorEntity[BeurerCosyNightCoordinator], SelectEntity):
    """Base class for Beurer CosyNight zone controls."""

    _attr_has_entity_name = True
    _attr_options = [str(x) for x in range(10)]

    def __init__(
        self,
        coordinator: BeurerCosyNightCoordinator,
        device: beurer_cosynight.Device,
        timer: TimerNumber,
        zone_type: str,
    ) -> None:
        super().__init__(coordinator)
        self._device = device
        self._timer = timer
        self._attr_name = zone_type
        self._attr_unique_id = (
            f"beurer_cosynight_{device.id}_{zone_type.lower().replace(' ', '_')}"
        )
        self._attr_device_info = device_info_for(device)

    @property
    def current_option(self) -> str:
        if self.coordinator.data is None:
            return "0"
        return str(self._get_setting())

    @abstractmethod
    def _get_setting(self) -> int: ...

    async def _async_quickstart(
        self, zone_body: int | None = None, zone_feet: int | None = None
    ) -> None:
        async with self.coordinator.quickstart_lock:
            data = self.coordinator.data
            body = (
                zone_body
                if zone_body is not None
                else (data.bodySetting if data else 0)
            )
            feet = (
                zone_feet
                if zone_feet is not None
                else (data.feetSetting if data else 0)
            )
            qs = beurer_cosynight.Quickstart(
                bodySetting=body,
                feetSetting=feet,
                id=self._device.id,
                timespan=self._timer.timespan_seconds,
            )
            await self.coordinator.execute_quickstart_unlocked(qs)


class BodyZone(_Zone):
    """Select entity for body zone heating level."""

    def __init__(
        self,
        coordinator: BeurerCosyNightCoordinator,
        device: beurer_cosynight.Device,
        timer: TimerNumber,
    ) -> None:
        super().__init__(coordinator, device, timer, "Body Zone")
        self._attr_icon = "mdi:human"

    def _get_setting(self) -> int:
        return self.coordinator.data.bodySetting

    async def async_select_option(self, option: str) -> None:
        await self._async_quickstart(zone_body=int(option))


class FeetZone(_Zone):
    """Select entity for feet zone heating level."""

    def __init__(
        self,
        coordinator: BeurerCosyNightCoordinator,
        device: beurer_cosynight.Device,
        timer: TimerNumber,
    ) -> None:
        super().__init__(coordinator, device, timer, "Feet Zone")
        self._attr_icon = "mdi:foot-print"

    def _get_setting(self) -> int:
        return self.coordinator.data.feetSetting

    async def async_select_option(self, option: str) -> None:
        await self._async_quickstart(zone_feet=int(option))
