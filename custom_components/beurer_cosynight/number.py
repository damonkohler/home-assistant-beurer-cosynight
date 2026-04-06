"""Number entities for Beurer CosyNight integration."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import beurer_cosynight
from .const import (
    DOMAIN,
    SECONDS_PER_MINUTE,
    TIMER_DEFAULT_MINUTES,
    TIMER_MAX_MINUTES,
    TIMER_MIN_MINUTES,
)
from .helpers import device_info_for


class TimerNumber(RestoreEntity, NumberEntity):
    """Number entity for session duration in minutes."""

    _attr_has_entity_name = True
    _attr_native_min_value = TIMER_MIN_MINUTES
    _attr_native_max_value = TIMER_MAX_MINUTES
    _attr_native_step = 1
    _attr_mode = NumberMode.BOX
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_icon = "mdi:timer-outline"
    _attr_name = "Timer"

    def __init__(self, device: beurer_cosynight.Device) -> None:
        self._attr_native_value = float(TIMER_DEFAULT_MINUTES)
        self._attr_unique_id = f"beurer_cosynight_{device.id}_timer"
        self._attr_device_info = device_info_for(device)

    @property
    def timespan_seconds(self) -> int:
        """Return the timer duration in seconds."""
        value = self.native_value
        if value is None:
            return TIMER_DEFAULT_MINUTES * SECONDS_PER_MINUTE
        return int(value) * SECONDS_PER_MINUTE

    async def async_set_native_value(self, value: float) -> None:
        """Set the timer value."""
        self._attr_native_value = value
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Restore last known value on startup."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state is None:
            return
        try:
            self._attr_native_value = float(last_state.state)
        except (ValueError, TypeError):
            self._attr_native_value = float(TIMER_DEFAULT_MINUTES)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Beurer CosyNight number entities from a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    timers: dict[str, TimerNumber] = data["timers"]
    async_add_entities(list(timers.values()))
