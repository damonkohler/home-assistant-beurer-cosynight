"""Tests for Beurer CosyNight select entities."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.exceptions import HomeAssistantError

from custom_components.beurer_cosynight.beurer_cosynight import (
    ApiError,
    AuthError,
    Device,
    Quickstart,
    Status,
)
from custom_components.beurer_cosynight.const import (
    DEFAULT_TIMER_LABEL,
    DOMAIN,
    TIMER_OPTIONS,
)
from custom_components.beurer_cosynight.select import (
    BodyZone,
    FeetZone,
    TimerSelect,
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
    """Return a mock coordinator with async hub and a real quickstart_lock."""
    coord = MagicMock()
    coord.data = status
    coord.hub = MagicMock()
    coord.hub.quickstart = AsyncMock()
    coord.async_request_refresh = AsyncMock()
    coord.quickstart_lock = asyncio.Lock()
    return coord


@pytest.fixture
def timer(device):
    return TimerSelect(device)


@pytest.fixture
def body_zone(coordinator, device, timer):
    zone = BodyZone(coordinator, device, timer)
    zone.hass = MagicMock()
    return zone


@pytest.fixture
def feet_zone(coordinator, device, timer):
    zone = FeetZone(coordinator, device, timer)
    zone.hass = MagicMock()
    return zone


class TestBodyZone:
    """Test BodyZone select entity."""

    def test_current_option_from_coordinator(self, body_zone):
        """Body zone should read bodySetting from coordinator data."""
        assert body_zone.current_option == "3"

    def test_current_option_none_data(self, body_zone, coordinator):
        """Should return '0' when coordinator data is None."""
        coordinator.data = None
        assert body_zone.current_option == "0"

    def test_options_range_0_to_9(self, body_zone):
        """Options should be '0' through '9'."""
        assert body_zone.options == [str(x) for x in range(10)]

    async def test_select_option_sends_quickstart(self, body_zone, coordinator):
        """Selecting an option should await hub.quickstart with correct body value."""
        await body_zone.async_select_option("7")

        coordinator.hub.quickstart.assert_awaited_once()
        qs = coordinator.hub.quickstart.call_args[0][0]
        assert isinstance(qs, Quickstart)
        assert qs.bodySetting == 7
        assert qs.feetSetting == 5  # keeps current feet value
        assert qs.id == MOCK_DEVICE_ID

    async def test_select_option_refreshes_coordinator(self, body_zone, coordinator):
        """Selecting an option should request coordinator refresh."""
        await body_zone.async_select_option("5")
        coordinator.async_request_refresh.assert_called_once()

    async def test_select_option_auth_error_raises_ha_error(
        self, body_zone, coordinator
    ):
        """AuthError from API should be wrapped in HomeAssistantError."""
        coordinator.hub.quickstart = AsyncMock(side_effect=AuthError("bad token"))
        with pytest.raises(HomeAssistantError, match="Authentication failed"):
            await body_zone.async_select_option("5")

    async def test_select_option_api_error_raises_ha_error(
        self, body_zone, coordinator
    ):
        """ApiError from API should be wrapped in HomeAssistantError."""
        coordinator.hub.quickstart = AsyncMock(side_effect=ApiError("timeout"))
        with pytest.raises(HomeAssistantError, match="API error"):
            await body_zone.async_select_option("5")

    async def test_select_option_uses_timer_timespan(
        self, body_zone, timer, coordinator
    ):
        """Quickstart should use the timer's current timespan."""
        timer._selected = "2 hours"
        await body_zone.async_select_option("5")

        qs = coordinator.hub.quickstart.call_args[0][0]
        assert qs.timespan == 7200  # 2 hours

    def test_unique_id(self, body_zone):
        """Unique ID should include device ID and zone type."""
        assert body_zone.unique_id == f"beurer_cosynight_{MOCK_DEVICE_ID}_body_zone"

    def test_has_entity_name(self, body_zone):
        """Should use has_entity_name pattern."""
        assert body_zone.has_entity_name is True

    def test_name(self, body_zone):
        """Name should be 'Body Zone'."""
        assert body_zone.name == "Body Zone"

    def test_device_info(self, body_zone):
        """Should have device_info with correct identifiers."""
        info = body_zone.device_info
        assert info is not None
        assert (DOMAIN, MOCK_DEVICE_ID) in info["identifiers"]
        assert info["manufacturer"] == "Beurer"
        assert info["model"] == "CosyNight"


class TestFeetZone:
    """Test FeetZone select entity."""

    def test_current_option_from_coordinator(self, feet_zone):
        """Feet zone should read feetSetting from coordinator data."""
        assert feet_zone.current_option == "5"

    def test_current_option_none_data(self, feet_zone, coordinator):
        """Should return '0' when coordinator data is None."""
        coordinator.data = None
        assert feet_zone.current_option == "0"

    async def test_select_option_sends_quickstart(self, feet_zone, coordinator):
        """Selecting an option should await hub.quickstart with correct feet value."""
        await feet_zone.async_select_option("8")

        qs = coordinator.hub.quickstart.call_args[0][0]
        assert qs.feetSetting == 8
        assert qs.bodySetting == 3  # keeps current body value
        assert qs.id == MOCK_DEVICE_ID

    async def test_select_option_refreshes_coordinator(self, feet_zone, coordinator):
        """Selecting an option should request coordinator refresh."""
        await feet_zone.async_select_option("8")
        coordinator.async_request_refresh.assert_called_once()

    async def test_select_option_no_data_uses_zero_for_body(
        self, feet_zone, coordinator
    ):
        """When coordinator data is None, body should default to 0."""
        coordinator.data = None
        await feet_zone.async_select_option("4")

        qs = coordinator.hub.quickstart.call_args[0][0]
        assert qs.bodySetting == 0
        assert qs.feetSetting == 4

    def test_unique_id(self, feet_zone):
        assert feet_zone.unique_id == f"beurer_cosynight_{MOCK_DEVICE_ID}_feet_zone"

    def test_name(self, feet_zone):
        assert feet_zone.name == "Feet Zone"


class TestTimerSelect:
    """Test TimerSelect entity."""

    def test_default_selection(self, timer):
        """Timer should default to DEFAULT_TIMER_LABEL."""
        assert timer.current_option == DEFAULT_TIMER_LABEL

    def test_options_match_timer_options(self, timer):
        """Timer options should match TIMER_OPTIONS keys."""
        assert timer.options == list(TIMER_OPTIONS.keys())

    def test_timespan_seconds_default(self, timer):
        """Default timespan should be 3600 (1 hour)."""
        assert timer.timespan_seconds == 3600

    def test_timespan_seconds_30_min(self, timer):
        timer._selected = "30 min"
        assert timer.timespan_seconds == 1800

    def test_timespan_seconds_4_hours(self, timer):
        timer._selected = "4 hours"
        assert timer.timespan_seconds == 14400

    def test_timespan_unknown_option_defaults_to_3600(self, timer):
        """Unknown option should fall back to 3600."""
        timer._selected = "unknown"
        assert timer.timespan_seconds == 3600

    async def test_select_option_updates_state(self, timer):
        """Selecting an option should update _selected."""
        timer.async_write_ha_state = MagicMock()
        await timer.async_select_option("2 hours")
        assert timer.current_option == "2 hours"
        timer.async_write_ha_state.assert_called_once()

    def test_unique_id(self, timer):
        assert timer.unique_id == f"beurer_cosynight_{MOCK_DEVICE_ID}_timer"

    def test_has_entity_name(self, timer):
        assert timer.has_entity_name is True

    def test_device_info(self, timer):
        info = timer.device_info
        assert (DOMAIN, MOCK_DEVICE_ID) in info["identifiers"]


class TestQuickstartLockSerialization:
    """Test that concurrent zone updates serialize via quickstart_lock."""

    async def test_concurrent_body_and_feet_updates_serialize(
        self, coordinator, device, timer
    ):
        """Body and feet zone updates should not overlap (lock serializes them)."""
        execution_order: list[str] = []

        call_count = 0

        async def slow_quickstart(qs: Quickstart) -> None:
            nonlocal call_count
            call_count += 1
            label = f"call{call_count}"
            execution_order.append(f"{label}_start")
            await asyncio.sleep(0.01)
            execution_order.append(f"{label}_end")

        coordinator.hub.quickstart = slow_quickstart

        body = BodyZone(coordinator, device, timer)
        body.hass = MagicMock()
        feet = FeetZone(coordinator, device, timer)
        feet.hass = MagicMock()

        await asyncio.gather(
            body.async_select_option("7"),
            feet.async_select_option("8"),
        )

        # With the lock, one must complete before the other starts.
        # Without the lock, we'd see interleaving like [start, start, end, end].
        start_indices = [
            i for i, v in enumerate(execution_order) if v.endswith("_start")
        ]
        end_indices = [i for i, v in enumerate(execution_order) if v.endswith("_end")]
        # First operation must end before second starts.
        assert end_indices[0] < start_indices[1]


class TestAsyncSetupEntry:
    """Test the platform async_setup_entry."""

    async def test_creates_entities_for_each_device(self, mock_hass, device, status):
        """Should create BodyZone, FeetZone, and TimerSelect per device."""
        coordinator = MagicMock()
        coordinator.data = status

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

        assert len(added_entities) == 3
        types = {type(e).__name__ for e in added_entities}
        assert types == {"BodyZone", "FeetZone", "TimerSelect"}
