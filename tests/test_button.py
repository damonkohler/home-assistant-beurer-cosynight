"""Tests for Beurer CosyNight button entity."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.exceptions import HomeAssistantError

from custom_components.beurer_cosynight.beurer_cosynight import (
    ApiError,
    AuthError,
    BeurerCosyNight,
    Device,
    Quickstart,
    Status,
)
from custom_components.beurer_cosynight.button import StopButton, async_setup_entry
from custom_components.beurer_cosynight.const import DOMAIN
from custom_components.beurer_cosynight.coordinator import BeurerCosyNightCoordinator

from .conftest import MOCK_DEVICE_ID, MOCK_DEVICE_NAME


@pytest.fixture
def device():
    return Device(
        active=True, id=MOCK_DEVICE_ID, name=MOCK_DEVICE_NAME, requiresUpdate=False
    )


@pytest.fixture
def hub():
    hub = MagicMock(spec=BeurerCosyNight)
    hub.quickstart = AsyncMock()
    return hub


@pytest.fixture
def coordinator(hub):
    coord = MagicMock(spec=BeurerCosyNightCoordinator)
    coord.hub = hub
    coord.async_request_refresh = AsyncMock()
    coord.async_set_updated_data = MagicMock()
    coord.quickstart_lock = asyncio.Lock()
    return coord


@pytest.fixture
def button(coordinator, device):
    btn = StopButton(coordinator, device)
    btn.hass = MagicMock()
    return btn


class TestStopButton:
    """Test StopButton entity."""

    async def test_press_sends_quickstart_with_zeros(self, button, hub):
        """Pressing stop should await hub.quickstart with body=0, feet=0, timespan=0."""
        await button.async_press()

        hub.quickstart.assert_awaited_once()
        qs = hub.quickstart.call_args[0][0]
        assert isinstance(qs, Quickstart)
        assert qs.bodySetting == 0
        assert qs.feetSetting == 0
        assert qs.timespan == 0
        assert qs.id == MOCK_DEVICE_ID

    async def test_press_updates_coordinator_from_response(self, button, coordinator):
        """Pressing stop should update coordinator data from the API response, not refresh."""
        await button.async_press()
        coordinator.async_set_updated_data.assert_called_once()
        coordinator.async_request_refresh.assert_not_called()

    async def test_stop_button_updates_coordinator_from_api_response(
        self, button, hub, coordinator
    ):
        """After async_press, coordinator.async_set_updated_data should be called
        with the Status returned by hub.quickstart. async_request_refresh should
        NOT be called."""
        returned_status = Status(
            active=False,
            bodySetting=0,
            feetSetting=0,
            heartbeat=100,
            id=MOCK_DEVICE_ID,
            name=MOCK_DEVICE_NAME,
            requiresUpdate=False,
            timer=0,
        )
        hub.quickstart = AsyncMock(return_value=returned_status)
        coordinator.async_request_refresh.reset_mock()

        await button.async_press()

        coordinator.async_set_updated_data.assert_called_once_with(returned_status)
        coordinator.async_request_refresh.assert_not_called()

    async def test_press_auth_error_raises_ha_error(self, button, hub):
        """AuthError from API should be wrapped in HomeAssistantError."""
        hub.quickstart = AsyncMock(side_effect=AuthError("bad token"))
        with pytest.raises(HomeAssistantError, match="Authentication failed"):
            await button.async_press()

    async def test_press_api_error_raises_ha_error(self, button, hub):
        """ApiError from API should be wrapped in HomeAssistantError."""
        hub.quickstart = AsyncMock(side_effect=ApiError("timeout"))
        with pytest.raises(HomeAssistantError, match="API error"):
            await button.async_press()

    def test_unique_id(self, button):
        assert button.unique_id == f"beurer_cosynight_{MOCK_DEVICE_ID}_stop"

    def test_name(self, button):
        assert button.name == "Stop"

    def test_has_entity_name(self, button):
        assert button.has_entity_name is True

    def test_device_info(self, button):
        info = button.device_info
        assert (DOMAIN, MOCK_DEVICE_ID) in info["identifiers"]
        assert info["manufacturer"] == "Beurer"
        assert info["model"] == "CosyNight"
        assert info["name"] == MOCK_DEVICE_NAME


class TestAsyncSetupEntry:
    """Test the platform async_setup_entry."""

    async def test_creates_stop_button_per_device(self, mock_hass, device, hub):
        """Should create one StopButton per device."""
        coordinator = MagicMock(spec=BeurerCosyNightCoordinator)
        coordinator.hub = hub
        mock_hass.data = {
            DOMAIN: {
                "entry1": {
                    "hub": hub,
                    "devices": [device],
                    "coordinators": {MOCK_DEVICE_ID: coordinator},
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
        assert isinstance(added_entities[0], StopButton)
