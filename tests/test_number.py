"""Tests for Beurer CosyNight number entities."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.components.number import NumberMode
from homeassistant.const import UnitOfTime

from custom_components.beurer_cosynight.beurer_cosynight import Device
from custom_components.beurer_cosynight.const import (
    DOMAIN,
    TIMER_DEFAULT_MINUTES,
    TIMER_MAX_MINUTES,
    TIMER_MIN_MINUTES,
)
from custom_components.beurer_cosynight.number import TimerNumber, async_setup_entry

from .conftest import MOCK_DEVICE_ID, MOCK_DEVICE_NAME


@pytest.fixture
def device():
    return Device(
        active=True, id=MOCK_DEVICE_ID, name=MOCK_DEVICE_NAME, requiresUpdate=False
    )


@pytest.fixture
def timer(device):
    return TimerNumber(device)


class TestTimerNumber:
    """Test TimerNumber entity."""

    def test_default_value(self, timer):
        """Timer should default to TIMER_DEFAULT_MINUTES (60)."""
        assert timer.native_value == TIMER_DEFAULT_MINUTES
        assert timer.native_value == 60

    def test_native_min_value(self, timer):
        """Minimum value should be TIMER_MIN_MINUTES (1)."""
        assert timer.native_min_value == TIMER_MIN_MINUTES
        assert timer.native_min_value == 1

    def test_native_max_value(self, timer):
        """Maximum value should be TIMER_MAX_MINUTES (240)."""
        assert timer.native_max_value == TIMER_MAX_MINUTES
        assert timer.native_max_value == 240

    def test_native_step(self, timer):
        """Step should be 1 (minute resolution)."""
        assert timer.native_step == 1

    def test_mode_is_box(self, timer):
        """Mode should be BOX for direct numeric input."""
        assert timer.mode == NumberMode.BOX

    def test_unit_of_measurement(self, timer):
        """Unit of measurement should be minutes."""
        assert timer.native_unit_of_measurement == UnitOfTime.MINUTES

    def test_timespan_seconds_default(self, timer):
        """Default timespan should be 3600 seconds (60 min * 60)."""
        assert timer.timespan_seconds == 3600

    def test_timespan_seconds_1_minute(self, timer):
        """1 minute should produce 60 seconds."""
        timer._attr_native_value = 1
        assert timer.timespan_seconds == 60

    def test_timespan_seconds_60_minutes(self, timer):
        """60 minutes should produce 3600 seconds."""
        timer._attr_native_value = 60
        assert timer.timespan_seconds == 3600

    def test_timespan_seconds_240_minutes(self, timer):
        """240 minutes should produce 14400 seconds."""
        timer._attr_native_value = 240
        assert timer.timespan_seconds == 14400

    def test_timespan_seconds_120_minutes(self, timer):
        """120 minutes should produce 7200 seconds."""
        timer._attr_native_value = 120.0
        assert timer.timespan_seconds == 7200

    def test_timespan_seconds_none_falls_back_to_default(self, timer):
        """When native_value is None, should fall back to default."""
        timer._attr_native_value = None
        assert timer.timespan_seconds == TIMER_DEFAULT_MINUTES * 60

    async def test_async_set_native_value_updates_value(self, timer):
        """Setting a value should update native_value."""
        timer.async_write_ha_state = MagicMock()
        await timer.async_set_native_value(120)
        assert timer.native_value == 120

    async def test_async_set_native_value_writes_state(self, timer):
        """Setting a value should call async_write_ha_state."""
        timer.async_write_ha_state = MagicMock()
        await timer.async_set_native_value(90)
        timer.async_write_ha_state.assert_called_once()

    def test_unique_id(self, timer):
        """Unique ID should preserve the existing pattern for migration."""
        assert timer.unique_id == f"beurer_cosynight_{MOCK_DEVICE_ID}_timer"

    def test_has_entity_name(self, timer):
        """Should use has_entity_name pattern."""
        assert timer.has_entity_name is True

    def test_name(self, timer):
        """Name should be 'Timer'."""
        assert timer.name == "Timer"

    def test_icon(self, timer):
        """Icon should be mdi:timer-outline."""
        assert timer.icon == "mdi:timer-outline"

    def test_device_info(self, timer):
        """Should have device_info with correct identifiers."""
        info = timer.device_info
        assert info is not None
        assert (DOMAIN, MOCK_DEVICE_ID) in info["identifiers"]
        assert info["manufacturer"] == "Beurer"
        assert info["model"] == "CosyNight"


class TestTimerNumberRestore:
    """Test TimerNumber state restoration via RestoreEntity."""

    async def test_restore_previous_value(self, device):
        """If last state exists, timer should restore that value."""
        timer = TimerNumber(device)
        timer.async_write_ha_state = MagicMock()

        # Simulate RestoreEntity returning a previous state of 120 minutes
        last_state = MagicMock()
        last_state.state = "120"
        timer.async_get_last_state = AsyncMock(return_value=last_state)

        await timer.async_added_to_hass()
        assert timer.native_value == 120

    async def test_restore_no_previous_state_uses_default(self, device):
        """If no last state exists, timer should use default (60)."""
        timer = TimerNumber(device)
        timer.async_write_ha_state = MagicMock()

        timer.async_get_last_state = AsyncMock(return_value=None)

        await timer.async_added_to_hass()
        assert timer.native_value == TIMER_DEFAULT_MINUTES

    async def test_restore_invalid_state_uses_default(self, device):
        """If last state is not a valid number, timer should use default."""
        timer = TimerNumber(device)
        timer.async_write_ha_state = MagicMock()

        last_state = MagicMock()
        last_state.state = "unavailable"
        timer.async_get_last_state = AsyncMock(return_value=last_state)

        await timer.async_added_to_hass()
        assert timer.native_value == TIMER_DEFAULT_MINUTES


class TestAsyncSetupEntry:
    """Test the number platform async_setup_entry."""

    async def test_creates_timer_entities_from_hass_data(self, mock_hass, device):
        """Should add all TimerNumber entities stored in hass.data."""
        timer = TimerNumber(device)
        mock_hass.data = {
            DOMAIN: {
                "entry1": {
                    "timers": {device.id: timer},
                }
            }
        }

        entry = MagicMock()
        entry.entry_id = "entry1"

        added_entities = []
        async_add_entities = MagicMock(
            side_effect=lambda entities: added_entities.extend(entities)
        )

        await async_setup_entry(mock_hass, entry, async_add_entities)

        assert len(added_entities) == 1
        assert added_entities[0] is timer

    async def test_creates_multiple_timers_for_multiple_devices(self, mock_hass):
        """Should add one TimerNumber per device."""
        device_a = Device(
            active=True, id="dev-a", name="Device A", requiresUpdate=False
        )
        device_b = Device(
            active=True, id="dev-b", name="Device B", requiresUpdate=False
        )
        timer_a = TimerNumber(device_a)
        timer_b = TimerNumber(device_b)

        mock_hass.data = {
            DOMAIN: {
                "entry1": {
                    "timers": {"dev-a": timer_a, "dev-b": timer_b},
                }
            }
        }

        entry = MagicMock()
        entry.entry_id = "entry1"

        added_entities = []
        async_add_entities = MagicMock(
            side_effect=lambda entities: added_entities.extend(entities)
        )

        await async_setup_entry(mock_hass, entry, async_add_entities)

        assert len(added_entities) == 2
        assert set(added_entities) == {timer_a, timer_b}
