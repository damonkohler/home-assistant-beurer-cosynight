"""Select entities for Beurer CosyNight integration."""

from __future__ import annotations

import logging

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import beurer_cosynight
from .const import DEFAULT_TIMER_LABEL, DOMAIN, TIMER_OPTIONS
from .coordinator import BeurerCosyNightCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Beurer CosyNight select entities from a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    devices: list[beurer_cosynight.Device] = data["devices"]
    coordinators: dict[str, BeurerCosyNightCoordinator] = data["coordinators"]

    entities: list[SelectEntity] = []
    for device in devices:
        coordinator = coordinators[device.id]
        timer = TimerSelect(device)
        entities.append(BodyZone(coordinator, device, timer))
        entities.append(FeetZone(coordinator, device, timer))
        entities.append(timer)
    async_add_entities(entities)


class _Zone(CoordinatorEntity[BeurerCosyNightCoordinator], SelectEntity):
    """Base class for Beurer CosyNight zone controls."""

    _attr_has_entity_name = True
    _attr_options = [str(x) for x in range(10)]

    def __init__(
        self,
        coordinator: BeurerCosyNightCoordinator,
        device: beurer_cosynight.Device,
        timer: TimerSelect,
        zone_type: str,
    ) -> None:
        super().__init__(coordinator)
        self._device = device
        self._timer = timer
        self._attr_name = zone_type
        self._attr_unique_id = (
            f"beurer_cosynight_{device.id}_{zone_type.lower().replace(' ', '_')}"
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.id)},
            name=device.name,
            manufacturer="Beurer",
            model="CosyNight",
        )

    @property
    def current_option(self) -> str:
        if self.coordinator.data is None:
            return "0"
        return str(self._get_setting())

    def _get_setting(self) -> int:
        raise NotImplementedError

    async def _async_quickstart(self, body: int, feet: int) -> None:
        qs = beurer_cosynight.Quickstart(
            bodySetting=body,
            feetSetting=feet,
            id=self._device.id,
            timespan=self._timer.timespan_seconds,
        )
        await self.hass.async_add_executor_job(self.coordinator.hub.quickstart, qs)
        await self.coordinator.async_request_refresh()


class BodyZone(_Zone):
    """Select entity for body zone heating level."""

    def __init__(self, coordinator, device, timer) -> None:
        super().__init__(coordinator, device, timer, "Body Zone")
        self._attr_icon = "mdi:human"

    def _get_setting(self) -> int:
        return self.coordinator.data.bodySetting

    async def async_select_option(self, option: str) -> None:
        data = self.coordinator.data
        feet = data.feetSetting if data else 0
        await self._async_quickstart(int(option), feet)


class FeetZone(_Zone):
    """Select entity for feet zone heating level."""

    def __init__(self, coordinator, device, timer) -> None:
        super().__init__(coordinator, device, timer, "Feet Zone")
        self._attr_icon = "mdi:foot-print"

    def _get_setting(self) -> int:
        return self.coordinator.data.feetSetting

    async def async_select_option(self, option: str) -> None:
        data = self.coordinator.data
        body = data.bodySetting if data else 0
        await self._async_quickstart(body, int(option))


class TimerSelect(SelectEntity):
    """Select entity for session duration."""

    _attr_has_entity_name = True
    _attr_options = list(TIMER_OPTIONS.keys())
    _attr_icon = "mdi:timer-outline"

    def __init__(self, device: beurer_cosynight.Device) -> None:
        self._selected = DEFAULT_TIMER_LABEL
        self._attr_name = "Timer"
        self._attr_unique_id = f"beurer_cosynight_{device.id}_timer"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.id)},
            name=device.name,
            manufacturer="Beurer",
            model="CosyNight",
        )

    @property
    def current_option(self) -> str:
        return self._selected

    @property
    def timespan_seconds(self) -> int:
        return TIMER_OPTIONS.get(self._selected, 3600)

    async def async_select_option(self, option: str) -> None:
        self._selected = option
        self.async_write_ha_state()
