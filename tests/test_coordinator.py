"""Tests for the Beurer CosyNight DataUpdateCoordinator."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from custom_components.beurer_cosynight.beurer_cosynight import (
    ApiError,
    AuthError,
    BeurerCosyNight,
    Quickstart,
    Status,
)
from custom_components.beurer_cosynight.coordinator import (
    BeurerCosyNightCoordinator,
    UPDATE_INTERVAL,
)

from .conftest import MOCK_DEVICE_ID, MOCK_DEVICE_NAME


class TestCoordinatorWiring:
    """Test coordinator correctly delegates to hub."""

    def test_update_interval_is_30_seconds(self):
        """Coordinator should poll every 30 seconds."""
        assert UPDATE_INTERVAL.total_seconds() == 30

    async def test_async_update_data_calls_get_status(self, mock_hass, mock_status):
        """_async_update_data should await hub.get_status directly."""
        hub = AsyncMock(spec=BeurerCosyNight)
        hub.get_status.return_value = mock_status

        coordinator = BeurerCosyNightCoordinator.__new__(BeurerCosyNightCoordinator)
        coordinator.hass = mock_hass
        coordinator.hub = hub
        coordinator.device_id = MOCK_DEVICE_ID

        result = await coordinator._async_update_data()

        hub.get_status.assert_awaited_once_with(MOCK_DEVICE_ID)
        assert result == mock_status

    async def test_auth_error_raises_config_entry_auth_failed(self, mock_hass):
        """AuthError from hub should raise ConfigEntryAuthFailed."""
        hub = AsyncMock(spec=BeurerCosyNight)
        hub.get_status.side_effect = AuthError("token expired")

        coordinator = BeurerCosyNightCoordinator.__new__(BeurerCosyNightCoordinator)
        coordinator.hass = mock_hass
        coordinator.hub = hub
        coordinator.device_id = MOCK_DEVICE_ID

        with pytest.raises(ConfigEntryAuthFailed):
            await coordinator._async_update_data()

    async def test_api_error_raises_update_failed(self, mock_hass):
        """ApiError from hub should raise UpdateFailed."""
        hub = AsyncMock(spec=BeurerCosyNight)
        hub.get_status.side_effect = ApiError("server error")

        coordinator = BeurerCosyNightCoordinator.__new__(BeurerCosyNightCoordinator)
        coordinator.hass = mock_hass
        coordinator.hub = hub
        coordinator.device_id = MOCK_DEVICE_ID

        with pytest.raises(UpdateFailed):
            await coordinator._async_update_data()

    def test_coordinator_stores_hub_and_device_id(self, mock_hass):
        """Coordinator should store hub reference and device_id."""
        hub = AsyncMock(spec=BeurerCosyNight)
        coordinator = BeurerCosyNightCoordinator.__new__(BeurerCosyNightCoordinator)
        coordinator.hub = hub
        coordinator.device_id = MOCK_DEVICE_ID
        assert coordinator.hub is hub
        assert coordinator.device_id == MOCK_DEVICE_ID


class TestQuickstartLock:
    """Test quickstart_lock on the coordinator.

    We patch DataUpdateCoordinator.__init__ to a no-op so we can call the
    real BeurerCosyNightCoordinator.__init__ without needing a fully
    initialized HA runtime.
    """

    def test_quickstart_lock_is_asyncio_lock(self, mock_hass):
        """Coordinator __init__ should create an asyncio.Lock for quickstart_lock."""
        hub = AsyncMock(spec=BeurerCosyNight)
        with patch.object(DataUpdateCoordinator, "__init__", return_value=None):
            coord = BeurerCosyNightCoordinator(
                mock_hass, hub, MOCK_DEVICE_ID, MOCK_DEVICE_NAME
            )
        assert isinstance(coord.quickstart_lock, asyncio.Lock)

    def test_quickstart_lock_is_not_shared_between_coordinators(self, mock_hass):
        """Each coordinator instance should have its own lock."""
        hub = AsyncMock(spec=BeurerCosyNight)
        with patch.object(DataUpdateCoordinator, "__init__", return_value=None):
            coord_a = BeurerCosyNightCoordinator(mock_hass, hub, "dev-a", "A")
            coord_b = BeurerCosyNightCoordinator(mock_hass, hub, "dev-b", "B")
        assert coord_a.quickstart_lock is not coord_b.quickstart_lock


class TestExecuteQuickstart:
    """Test the execute_quickstart method on the coordinator."""

    @pytest.fixture
    def coordinator(self, mock_hass):
        """Return a coordinator with mocked hub."""
        hub = AsyncMock(spec=BeurerCosyNight)
        coord = BeurerCosyNightCoordinator.__new__(BeurerCosyNightCoordinator)
        coord.hass = mock_hass
        coord.hub = hub
        coord.device_id = MOCK_DEVICE_ID
        coord.quickstart_lock = asyncio.Lock()
        coord.async_set_updated_data = MagicMock()
        return coord

    @pytest.fixture
    def quickstart(self):
        """Return a sample Quickstart."""
        return Quickstart(
            bodySetting=5,
            feetSetting=3,
            id=MOCK_DEVICE_ID,
            timespan=3600,
        )

    @pytest.fixture
    def returned_status(self):
        """Return a sample Status for hub.quickstart to return."""
        return Status(
            active=True,
            bodySetting=5,
            feetSetting=3,
            heartbeat=100,
            id=MOCK_DEVICE_ID,
            name=MOCK_DEVICE_NAME,
            requiresUpdate=False,
            timer=3600,
        )

    async def test_calls_hub_quickstart(self, coordinator, quickstart, returned_status):
        """Should call hub.quickstart with the given Quickstart."""
        coordinator.hub.quickstart.return_value = returned_status
        await coordinator.execute_quickstart(quickstart)

        coordinator.hub.quickstart.assert_awaited_once_with(quickstart)

    async def test_updates_coordinator_data(
        self, coordinator, quickstart, returned_status
    ):
        """Should call async_set_updated_data with the API response."""
        coordinator.hub.quickstart.return_value = returned_status
        await coordinator.execute_quickstart(quickstart)

        coordinator.async_set_updated_data.assert_called_once_with(returned_status)

    async def test_acquires_lock(self, coordinator, quickstart, returned_status):
        """Should hold the quickstart_lock during the API call."""
        lock_was_held = False

        async def check_lock(qs):
            nonlocal lock_was_held
            lock_was_held = coordinator.quickstart_lock.locked()
            return returned_status

        coordinator.hub.quickstart.side_effect = check_lock
        await coordinator.execute_quickstart(quickstart)

        assert lock_was_held

    async def test_auth_error_raises_ha_error(self, coordinator, quickstart):
        """AuthError from hub should be wrapped in HomeAssistantError."""
        coordinator.hub.quickstart.side_effect = AuthError("bad token")
        with pytest.raises(HomeAssistantError, match="Authentication failed"):
            await coordinator.execute_quickstart(quickstart)

    async def test_api_error_raises_ha_error(self, coordinator, quickstart):
        """ApiError from hub should be wrapped in HomeAssistantError."""
        coordinator.hub.quickstart.side_effect = ApiError("timeout")
        with pytest.raises(HomeAssistantError, match="API error"):
            await coordinator.execute_quickstart(quickstart)

    async def test_does_not_update_data_on_error(self, coordinator, quickstart):
        """On API error, should not call async_set_updated_data."""
        coordinator.hub.quickstart.side_effect = ApiError("fail")
        with pytest.raises(HomeAssistantError):
            await coordinator.execute_quickstart(quickstart)

        coordinator.async_set_updated_data.assert_not_called()

    async def test_concurrent_calls_serialize(
        self, coordinator, quickstart, returned_status
    ):
        """Two concurrent execute_quickstart calls should not overlap."""
        execution_log: list[str] = []

        async def slow_quickstart(qs):
            execution_log.append("start")
            await asyncio.sleep(0.01)
            execution_log.append("end")
            return returned_status

        coordinator.hub.quickstart.side_effect = slow_quickstart

        await asyncio.gather(
            coordinator.execute_quickstart(quickstart),
            coordinator.execute_quickstart(quickstart),
        )

        assert execution_log == ["start", "end", "start", "end"]


class TestExecuteQuickstartUnlocked:
    """Test execute_quickstart_unlocked (caller must hold lock)."""

    @pytest.fixture
    def coordinator(self, mock_hass):
        """Return a coordinator with mocked hub."""
        hub = AsyncMock(spec=BeurerCosyNight)
        coord = BeurerCosyNightCoordinator.__new__(BeurerCosyNightCoordinator)
        coord.hass = mock_hass
        coord.hub = hub
        coord.device_id = MOCK_DEVICE_ID
        coord.quickstart_lock = asyncio.Lock()
        coord.async_set_updated_data = MagicMock()
        return coord

    @pytest.fixture
    def quickstart(self):
        """Return a sample Quickstart."""
        return Quickstart(
            bodySetting=5,
            feetSetting=3,
            id=MOCK_DEVICE_ID,
            timespan=3600,
        )

    @pytest.fixture
    def returned_status(self):
        """Return a sample Status."""
        return Status(
            active=True,
            bodySetting=5,
            feetSetting=3,
            heartbeat=100,
            id=MOCK_DEVICE_ID,
            name=MOCK_DEVICE_NAME,
            requiresUpdate=False,
            timer=3600,
        )

    async def test_calls_hub_quickstart(self, coordinator, quickstart, returned_status):
        """Should call hub.quickstart with the given Quickstart."""
        coordinator.hub.quickstart.return_value = returned_status
        async with coordinator.quickstart_lock:
            await coordinator.execute_quickstart_unlocked(quickstart)

        coordinator.hub.quickstart.assert_awaited_once_with(quickstart)

    async def test_updates_coordinator_data(
        self, coordinator, quickstart, returned_status
    ):
        """Should call async_set_updated_data with the API response."""
        coordinator.hub.quickstart.return_value = returned_status
        async with coordinator.quickstart_lock:
            await coordinator.execute_quickstart_unlocked(quickstart)

        coordinator.async_set_updated_data.assert_called_once_with(returned_status)

    async def test_does_not_acquire_lock(
        self, coordinator, quickstart, returned_status
    ):
        """Should NOT try to acquire the lock itself (caller holds it)."""
        coordinator.hub.quickstart.return_value = returned_status
        # Acquire the lock externally. If _unlocked tried to acquire,
        # it would deadlock (asyncio.Lock is not reentrant).
        async with coordinator.quickstart_lock:
            # If this deadlocks, the test times out -- proving the
            # method does not try to re-acquire the lock.
            await coordinator.execute_quickstart_unlocked(quickstart)

    async def test_auth_error_raises_ha_error(self, coordinator, quickstart):
        """AuthError should be wrapped in HomeAssistantError."""
        coordinator.hub.quickstart.side_effect = AuthError("bad token")
        with pytest.raises(HomeAssistantError, match="Authentication failed"):
            await coordinator.execute_quickstart_unlocked(quickstart)

    async def test_api_error_raises_ha_error(self, coordinator, quickstart):
        """ApiError should be wrapped in HomeAssistantError."""
        coordinator.hub.quickstart.side_effect = ApiError("timeout")
        with pytest.raises(HomeAssistantError, match="API error"):
            await coordinator.execute_quickstart_unlocked(quickstart)
