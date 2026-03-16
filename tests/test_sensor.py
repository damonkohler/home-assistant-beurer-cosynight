"""Tests for Beurer CosyNight sensor entity."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import UnitOfTime

from custom_components.beurer_cosynight.beurer_cosynight import Device, Status
from custom_components.beurer_cosynight.const import DOMAIN
from custom_components.beurer_cosynight.sensor import (
    DeviceTimerSensor,
    async_setup_entry,
)

from .conftest import MOCK_DEVICE_ID, MOCK_DEVICE_NAME


@pytest.fixture
def device():
    return Device(
        active=True, id=MOCK_DEVICE_ID, name=MOCK_DEVICE_NAME, requiresUpdate=False
    )


@pytest.fixture
def status():
    return Status(
        active=True,
        bodySetting=3,
        feetSetting=5,
        heartbeat=100,
        id=MOCK_DEVICE_ID,
        name=MOCK_DEVICE_NAME,
        requiresUpdate=False,
        timer=1800,
    )


@pytest.fixture
def coordinator(status):
    coord = MagicMock()
    coord.data = status
    return coord


@pytest.fixture
def sensor(coordinator, device):
    return DeviceTimerSensor(coordinator, device)


class TestDeviceTimerSensor:
    """Test DeviceTimerSensor entity."""

    def test_native_value_returns_timer_seconds(self, sensor):
        """native_value should return the timer field from coordinator data."""
        assert sensor.native_value == 1800

    def test_native_value_zero_when_off(self, sensor, coordinator):
        """native_value should be 0 when device timer is 0."""
        coordinator.data = Status(
            active=False,
            bodySetting=0,
            feetSetting=0,
            heartbeat=0,
            id=MOCK_DEVICE_ID,
            name=MOCK_DEVICE_NAME,
            requiresUpdate=False,
            timer=0,
        )
        assert sensor.native_value == 0

    def test_native_value_none_when_no_data(self, sensor, coordinator):
        """native_value should be None when coordinator data is None."""
        coordinator.data = None
        assert sensor.native_value is None

    def test_device_class_is_duration(self, sensor):
        """Device class should be DURATION."""
        assert sensor.device_class == SensorDeviceClass.DURATION

    def test_unit_is_seconds(self, sensor):
        """Unit of measurement should be seconds."""
        assert sensor.native_unit_of_measurement == UnitOfTime.SECONDS

    def test_unique_id(self, sensor):
        assert sensor.unique_id == f"beurer_cosynight_{MOCK_DEVICE_ID}_remaining_time"

    def test_name(self, sensor):
        assert sensor.name == "Remaining Time"

    def test_has_entity_name(self, sensor):
        assert sensor.has_entity_name is True

    def test_device_info(self, sensor):
        info = sensor.device_info
        assert (DOMAIN, MOCK_DEVICE_ID) in info["identifiers"]
        assert info["manufacturer"] == "Beurer"
        assert info["model"] == "CosyNight"

    def test_native_value_changes_with_coordinator_data(self, sensor, coordinator):
        """Sensor should reflect updated coordinator data."""
        coordinator.data = Status(
            active=True,
            bodySetting=3,
            feetSetting=5,
            heartbeat=100,
            id=MOCK_DEVICE_ID,
            name=MOCK_DEVICE_NAME,
            requiresUpdate=False,
            timer=900,
        )
        assert sensor.native_value == 900


class TestAsyncSetupEntry:
    """Test the platform async_setup_entry."""

    @pytest.mark.asyncio
    async def test_creates_sensor_per_device(self, mock_hass, device, coordinator):
        """Should create one DeviceTimerSensor per device."""
        mock_hass.data = {
            DOMAIN: {
                "entry1": {
                    "devices": [device],
                    "coordinators": {device.id: coordinator},
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
        assert isinstance(added_entities[0], DeviceTimerSensor)
