"""Tests for Beurer CosyNight integration setup and unload."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import voluptuous as vol
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
    HomeAssistantError,
)

from custom_components.beurer_cosynight import (
    PLATFORMS,
    QUICKSTART_SCHEMA,
    async_setup_entry,
    async_unload_entry,
)
from custom_components.beurer_cosynight.beurer_cosynight import (
    ApiError,
    AuthError,
    Quickstart,
    Status,
)
from custom_components.beurer_cosynight.const import (
    DEFAULT_TIMER_LABEL,
    DOMAIN,
    TIMER_OPTIONS,
)

from .conftest import (
    MOCK_DEVICE_ID,
    MOCK_ENTRY_ID,
    MOCK_PASSWORD,
    MOCK_USERNAME,
)


@pytest.fixture
def mock_entry():
    """Return a mock config entry."""
    entry = MagicMock()
    entry.data = {"username": MOCK_USERNAME, "password": MOCK_PASSWORD}
    entry.entry_id = MOCK_ENTRY_ID
    return entry


@pytest.fixture(autouse=True)
def _patch_session():
    """Patch async_get_clientsession to avoid HA network stack in tests."""
    with patch(
        "custom_components.beurer_cosynight.async_get_clientsession",
        return_value=MagicMock(),
    ):
        yield


HA_DEVICE_ID = "ha-device-uuid-001"
"""HA device registry ID (distinct from the Beurer device_id)."""


@pytest.fixture
def mock_device_entry():
    """Return a mock HA device registry entry with Beurer identifiers."""
    entry = MagicMock()
    entry.identifiers = {(DOMAIN, MOCK_DEVICE_ID)}
    return entry


@pytest.fixture
def mock_device_registry(mock_device_entry):
    """Return a mock device registry that resolves HA_DEVICE_ID."""
    reg = MagicMock()
    reg.async_get.return_value = mock_device_entry
    return reg


class TestAsyncSetupEntry:
    """Test async_setup_entry with async hub."""

    async def test_auth_error_raises_config_entry_auth_failed(
        self, mock_hass, mock_entry
    ):
        """AuthError from hub should raise ConfigEntryAuthFailed."""
        with patch("custom_components.beurer_cosynight.BeurerCosyNight") as MockHub:
            MockHub.return_value.authenticate = AsyncMock(
                side_effect=AuthError("Invalid credentials")
            )
            with pytest.raises(ConfigEntryAuthFailed):
                await async_setup_entry(mock_hass, mock_entry)

    async def test_api_error_raises_config_entry_not_ready(self, mock_hass, mock_entry):
        """ApiError from hub should raise ConfigEntryNotReady."""
        with patch("custom_components.beurer_cosynight.BeurerCosyNight") as MockHub:
            MockHub.return_value.authenticate = AsyncMock(
                side_effect=ApiError("Connection failed")
            )
            with pytest.raises(ConfigEntryNotReady):
                await async_setup_entry(mock_hass, mock_entry)

    async def test_successful_setup(self, mock_hass, mock_entry, mock_hub_async):
        """Successful setup should store hub, devices, and coordinators."""
        with (
            patch(
                "custom_components.beurer_cosynight.BeurerCosyNight",
                return_value=mock_hub_async,
            ),
            patch(
                "custom_components.beurer_cosynight.BeurerCosyNightCoordinator"
            ) as MockCoord,
        ):
            coord_instance = AsyncMock()
            MockCoord.return_value = coord_instance
            result = await async_setup_entry(mock_hass, mock_entry)

        assert result is True
        mock_hub_async.authenticate.assert_awaited_once()
        mock_hub_async.list_devices.assert_awaited_once()

    async def test_no_executor_job_for_authenticate(
        self, mock_hass, mock_entry, mock_hub_async
    ):
        """Setup should await hub.authenticate directly, not via executor."""
        with (
            patch(
                "custom_components.beurer_cosynight.BeurerCosyNight",
                return_value=mock_hub_async,
            ),
            patch(
                "custom_components.beurer_cosynight.BeurerCosyNightCoordinator"
            ) as MockCoord,
        ):
            MockCoord.return_value = AsyncMock()
            await async_setup_entry(mock_hass, mock_entry)

        mock_hub_async.authenticate.assert_awaited_once()

    async def test_no_executor_job_for_list_devices(
        self, mock_hass, mock_entry, mock_hub_async
    ):
        """Setup should await hub.list_devices directly."""
        with (
            patch(
                "custom_components.beurer_cosynight.BeurerCosyNight",
                return_value=mock_hub_async,
            ),
            patch(
                "custom_components.beurer_cosynight.BeurerCosyNightCoordinator"
            ) as MockCoord,
        ):
            MockCoord.return_value = AsyncMock()
            await async_setup_entry(mock_hass, mock_entry)

        mock_hub_async.list_devices.assert_awaited_once()

    async def test_setup_registers_quickstart_service(
        self, mock_hass, mock_entry, mock_hub_async
    ):
        """Successful setup should register the quickstart service."""
        mock_hass.services.has_service.return_value = False
        with (
            patch(
                "custom_components.beurer_cosynight.BeurerCosyNight",
                return_value=mock_hub_async,
            ),
            patch(
                "custom_components.beurer_cosynight.BeurerCosyNightCoordinator"
            ) as MockCoord,
        ):
            MockCoord.return_value = AsyncMock()
            await async_setup_entry(mock_hass, mock_entry)

        mock_hass.services.async_register.assert_called_once()
        call_args = mock_hass.services.async_register.call_args
        assert call_args[0][0] == DOMAIN
        assert call_args[0][1] == "quickstart"

    async def test_setup_does_not_re_register_quickstart_service(
        self, mock_hass, mock_entry, mock_hub_async
    ):
        """When quickstart service already exists, setup should not register again."""
        mock_hass.services.has_service.return_value = True
        with (
            patch(
                "custom_components.beurer_cosynight.BeurerCosyNight",
                return_value=mock_hub_async,
            ),
            patch(
                "custom_components.beurer_cosynight.BeurerCosyNightCoordinator"
            ) as MockCoord,
        ):
            MockCoord.return_value = AsyncMock()
            await async_setup_entry(mock_hass, mock_entry)

        mock_hass.services.async_register.assert_not_called()


class TestAsyncUnloadEntry:
    """Test async_unload_entry."""

    async def test_unload_removes_data(self, mock_hass):
        """Successful unload should remove entry data from hass.data."""
        mock_entry = MagicMock()
        mock_entry.entry_id = "test_entry"
        mock_hass.data = {DOMAIN: {"test_entry": {"hub": MagicMock()}}}

        result = await async_unload_entry(mock_hass, mock_entry)

        assert result is True
        assert "test_entry" not in mock_hass.data[DOMAIN]

    async def test_unload_failure_keeps_data(self, mock_hass):
        """Failed unload should keep entry data."""
        mock_entry = MagicMock()
        mock_entry.entry_id = "test_entry"
        mock_hass.data = {DOMAIN: {"test_entry": {"hub": MagicMock()}}}
        mock_hass.config_entries.async_unload_platforms = AsyncMock(return_value=False)

        result = await async_unload_entry(mock_hass, mock_entry)

        assert result is False
        assert "test_entry" in mock_hass.data[DOMAIN]

    async def test_unload_last_entry_removes_quickstart_service(self, mock_hass):
        """Unloading the last entry should remove the quickstart service."""
        mock_entry = MagicMock()
        mock_entry.entry_id = "test_entry"
        # Only one entry -- after removal the DOMAIN dict is empty.
        mock_hass.data = {DOMAIN: {"test_entry": {"hub": MagicMock()}}}

        result = await async_unload_entry(mock_hass, mock_entry)

        assert result is True
        mock_hass.services.async_remove.assert_called_once_with(DOMAIN, "quickstart")

    async def test_unload_non_last_entry_keeps_quickstart_service(self, mock_hass):
        """Unloading an entry when other entries remain should keep the service."""
        mock_entry = MagicMock()
        mock_entry.entry_id = "entry_a"
        mock_hass.data = {
            DOMAIN: {
                "entry_a": {"hub": MagicMock()},
                "entry_b": {"hub": MagicMock()},
            }
        }

        result = await async_unload_entry(mock_hass, mock_entry)

        assert result is True
        mock_hass.services.async_remove.assert_not_called()


class TestQuickstartService:
    """Test the beurer_cosynight.quickstart service handler.

    The handler is a closure inside async_setup_entry. To test it, we
    perform a real setup with mocked hub/coordinator, capture the handler
    registered via hass.services.async_register, and invoke it directly.
    """

    @pytest.fixture
    def coordinator(self, mock_hub_async):
        """Return a mock coordinator with a real asyncio.Lock."""
        coord = AsyncMock()
        coord.hub = mock_hub_async
        coord.quickstart_lock = asyncio.Lock()
        coord.async_request_refresh = AsyncMock()
        coord.async_set_updated_data = MagicMock()
        return coord

    @pytest.fixture
    async def quickstart_setup(
        self, mock_hass, mock_entry, mock_hub_async, coordinator, mock_device_registry
    ):
        """Set up the integration and return (handler, dr_patch) for handler tests.

        The dr.async_get patch must remain active when the handler is called
        (not just during setup), because the handler resolves the device
        registry at call time via dr.async_get(hass).
        """
        mock_hass.services.has_service.return_value = False

        dr_patcher = patch(
            "custom_components.beurer_cosynight.dr.async_get",
            return_value=mock_device_registry,
        )
        dr_patcher.start()

        with (
            patch(
                "custom_components.beurer_cosynight.BeurerCosyNight",
                return_value=mock_hub_async,
            ),
            patch(
                "custom_components.beurer_cosynight.BeurerCosyNightCoordinator",
                return_value=coordinator,
            ),
        ):
            await async_setup_entry(mock_hass, mock_entry)

        handler = mock_hass.services.async_register.call_args[0][2]
        yield handler
        dr_patcher.stop()

    @pytest.fixture
    def quickstart_handler(self, quickstart_setup):
        """Return just the handler for convenience."""
        return quickstart_setup

    def _make_call(self, **kwargs) -> MagicMock:
        """Create a mock ServiceCall with given data."""
        call = MagicMock()
        call.data = kwargs
        return call

    async def test_happy_path_sends_quickstart_api_call(
        self, quickstart_handler, mock_hub_async, coordinator
    ):
        """Valid call should send quickstart with correct body/feet/timer."""
        call = self._make_call(device_id=HA_DEVICE_ID, body=7, feet=3, timer="2 hours")
        await quickstart_handler(call)

        mock_hub_async.quickstart.assert_awaited_once()
        qs = mock_hub_async.quickstart.call_args[0][0]
        assert isinstance(qs, Quickstart)
        assert qs.bodySetting == 7
        assert qs.feetSetting == 3
        assert qs.id == MOCK_DEVICE_ID
        assert qs.timespan == 7200  # 2 hours

    async def test_happy_path_updates_coordinator_from_response(
        self, quickstart_handler, coordinator
    ):
        """After quickstart API call, coordinator should be updated from the API response."""
        call = self._make_call(device_id=HA_DEVICE_ID, body=5, feet=5)
        await quickstart_handler(call)

        coordinator.async_set_updated_data.assert_called_once()
        coordinator.async_request_refresh.assert_not_called()

    async def test_quickstart_service_updates_coordinator_from_api_response(
        self, quickstart_handler, mock_hub_async, coordinator
    ):
        """After the handle_quickstart service call, coordinator.async_set_updated_data
        should be called with the Status returned by hub.quickstart.
        async_request_refresh should NOT be called."""
        returned_status = Status(
            active=True,
            bodySetting=5,
            feetSetting=5,
            heartbeat=100,
            id=MOCK_DEVICE_ID,
            name="Test",
            requiresUpdate=False,
            timer=3600,
        )
        mock_hub_async.quickstart = AsyncMock(return_value=returned_status)
        coordinator.async_request_refresh.reset_mock()

        call = self._make_call(device_id=HA_DEVICE_ID, body=5, feet=5)
        await quickstart_handler(call)

        coordinator.async_set_updated_data.assert_called_once_with(returned_status)
        coordinator.async_request_refresh.assert_not_called()

    async def test_default_timer_when_omitted(self, quickstart_handler, mock_hub_async):
        """Omitting timer should use DEFAULT_TIMER_LABEL (1 hour = 3600s)."""
        call = self._make_call(device_id=HA_DEVICE_ID, body=5, feet=5)
        await quickstart_handler(call)

        qs = mock_hub_async.quickstart.call_args[0][0]
        assert qs.timespan == TIMER_OPTIONS[DEFAULT_TIMER_LABEL]

    async def test_each_timer_label_maps_to_correct_seconds(
        self, quickstart_handler, mock_hub_async
    ):
        """Each timer label in TIMER_OPTIONS should produce the right timespan."""
        for label, expected_seconds in TIMER_OPTIONS.items():
            mock_hub_async.quickstart.reset_mock()
            call = self._make_call(device_id=HA_DEVICE_ID, body=1, feet=1, timer=label)
            await quickstart_handler(call)

            qs = mock_hub_async.quickstart.call_args[0][0]
            assert qs.timespan == expected_seconds, f"Failed for timer={label!r}"

    async def test_device_not_found_raises(
        self, quickstart_handler, mock_device_registry
    ):
        """Unknown device_id should raise HomeAssistantError."""
        mock_device_registry.async_get.return_value = None
        call = self._make_call(device_id="nonexistent", body=5, feet=5)

        with pytest.raises(HomeAssistantError, match="not found"):
            await quickstart_handler(call)

    async def test_non_beurer_device_raises(
        self, quickstart_handler, mock_device_entry
    ):
        """Device without a Beurer identifier should raise HomeAssistantError."""
        mock_device_entry.identifiers = {("other_integration", "some-id")}
        call = self._make_call(device_id=HA_DEVICE_ID, body=5, feet=5)

        with pytest.raises(HomeAssistantError, match="not a Beurer CosyNight device"):
            await quickstart_handler(call)

    async def test_no_coordinator_for_device_raises(
        self, mock_hass, mock_entry, mock_hub_async, mock_device_registry
    ):
        """Device with Beurer identifier but no coordinator should raise HomeAssistantError.

        This can happen if the device belongs to a different config entry than
        the one that registered the coordinators being searched.
        """
        coord = AsyncMock()
        coord.hub = mock_hub_async
        coord.quickstart_lock = asyncio.Lock()
        mock_hass.services.has_service.return_value = False

        # Keep dr.async_get patched for the handler invocation (not just setup).
        with (
            patch(
                "custom_components.beurer_cosynight.BeurerCosyNight",
                return_value=mock_hub_async,
            ),
            patch(
                "custom_components.beurer_cosynight.BeurerCosyNightCoordinator",
                return_value=coord,
            ),
            patch(
                "custom_components.beurer_cosynight.dr.async_get",
                return_value=mock_device_registry,
            ),
        ):
            # The mock_hub_async returns a device with MOCK_DEVICE_ID,
            # so coordinators maps MOCK_DEVICE_ID -> coord.
            await async_setup_entry(mock_hass, mock_entry)

            handler = mock_hass.services.async_register.call_args[0][2]

            # Return a Beurer device with a DIFFERENT id than what was set up.
            other_entry = MagicMock()
            other_entry.identifiers = {(DOMAIN, "device-xyz-999")}
            mock_device_registry.async_get.return_value = other_entry

            call = MagicMock()
            call.data = {"device_id": HA_DEVICE_ID, "body": 5, "feet": 5}

            with pytest.raises(HomeAssistantError, match="No coordinator"):
                await handler(call)

    async def test_quickstart_acquires_lock(
        self, quickstart_handler, mock_hub_async, coordinator
    ):
        """Quickstart handler should hold the coordinator lock during API call."""
        lock_was_held = False

        async def check_lock(qs):
            nonlocal lock_was_held
            lock_was_held = coordinator.quickstart_lock.locked()

        mock_hub_async.quickstart.side_effect = check_lock
        call = self._make_call(device_id=HA_DEVICE_ID, body=5, feet=5)
        await quickstart_handler(call)

        assert lock_was_held, "Lock should be held during hub.quickstart()"

    async def test_concurrent_quickstart_calls_serialize(
        self, quickstart_handler, mock_hub_async, coordinator
    ):
        """Two concurrent quickstart calls should not overlap."""
        execution_log: list[str] = []

        async def slow_quickstart(qs):
            execution_log.append("start")
            await asyncio.sleep(0.01)
            execution_log.append("end")

        mock_hub_async.quickstart.side_effect = slow_quickstart

        call_a = self._make_call(device_id=HA_DEVICE_ID, body=3, feet=3)
        call_b = self._make_call(device_id=HA_DEVICE_ID, body=7, feet=7)

        await asyncio.gather(
            quickstart_handler(call_a),
            quickstart_handler(call_b),
        )

        assert execution_log == ["start", "end", "start", "end"]

    async def test_body_and_feet_are_passed_as_integers(
        self, quickstart_handler, mock_hub_async
    ):
        """body and feet should be coerced to int in the Quickstart payload."""
        # The voluptuous schema does Coerce(int), but the handler also
        # does int(call.data["body"]). Verify the final value is int.
        call = self._make_call(device_id=HA_DEVICE_ID, body="4", feet="6")
        await quickstart_handler(call)

        qs = mock_hub_async.quickstart.call_args[0][0]
        assert isinstance(qs.bodySetting, int)
        assert isinstance(qs.feetSetting, int)
        assert qs.bodySetting == 4
        assert qs.feetSetting == 6

    async def test_body_zero_and_feet_zero(self, quickstart_handler, mock_hub_async):
        """Setting both zones to 0 should still send a valid quickstart (stop)."""
        call = self._make_call(device_id=HA_DEVICE_ID, body=0, feet=0)
        await quickstart_handler(call)

        qs = mock_hub_async.quickstart.call_args[0][0]
        assert qs.bodySetting == 0
        assert qs.feetSetting == 0

    async def test_body_max_and_feet_max(self, quickstart_handler, mock_hub_async):
        """Maximum zone values (9) should be accepted."""
        call = self._make_call(device_id=HA_DEVICE_ID, body=9, feet=9)
        await quickstart_handler(call)

        qs = mock_hub_async.quickstart.call_args[0][0]
        assert qs.bodySetting == 9
        assert qs.feetSetting == 9

    async def test_auth_error_raises_ha_error(self, quickstart_handler, mock_hub_async):
        """AuthError from API should be wrapped in HomeAssistantError."""
        mock_hub_async.quickstart = AsyncMock(side_effect=AuthError("bad token"))
        call = self._make_call(device_id=HA_DEVICE_ID, body=5, feet=5)
        with pytest.raises(HomeAssistantError, match="Authentication failed"):
            await quickstart_handler(call)

    async def test_api_error_raises_ha_error(self, quickstart_handler, mock_hub_async):
        """ApiError from API should be wrapped in HomeAssistantError."""
        mock_hub_async.quickstart = AsyncMock(side_effect=ApiError("timeout"))
        call = self._make_call(device_id=HA_DEVICE_ID, body=5, feet=5)
        with pytest.raises(HomeAssistantError, match="API error"):
            await quickstart_handler(call)


class TestQuickstartServiceSchema:
    """Test the voluptuous schema for the quickstart service."""

    @pytest.fixture
    def schema(self):
        """Return the actual quickstart schema from the module."""
        return QUICKSTART_SCHEMA

    def test_valid_minimal_input(self, schema):
        """Minimum required fields should validate."""
        result = schema({"device_id": "dev-1", "body": 5, "feet": 3})
        assert result["device_id"] == "dev-1"
        assert result["body"] == 5
        assert result["feet"] == 3

    def test_valid_with_timer(self, schema):
        """Timer field should accept known labels."""
        result = schema(
            {"device_id": "dev-1", "body": 5, "feet": 3, "timer": "2 hours"}
        )
        assert result["timer"] == "2 hours"

    def test_body_coerced_from_string(self, schema):
        """String body value should be coerced to int."""
        result = schema({"device_id": "dev-1", "body": "7", "feet": 3})
        assert result["body"] == 7

    def test_body_below_range_rejects(self, schema):
        """body < 0 should be rejected."""
        with pytest.raises(vol.Invalid):
            schema({"device_id": "dev-1", "body": -1, "feet": 3})

    def test_body_above_range_rejects(self, schema):
        """body > 9 should be rejected."""
        with pytest.raises(vol.Invalid):
            schema({"device_id": "dev-1", "body": 10, "feet": 3})

    def test_feet_below_range_rejects(self, schema):
        """feet < 0 should be rejected."""
        with pytest.raises(vol.Invalid):
            schema({"device_id": "dev-1", "body": 3, "feet": -1})

    def test_feet_above_range_rejects(self, schema):
        """feet > 9 should be rejected."""
        with pytest.raises(vol.Invalid):
            schema({"device_id": "dev-1", "body": 3, "feet": 10})

    def test_invalid_timer_rejects(self, schema):
        """Unknown timer label should be rejected."""
        with pytest.raises(vol.Invalid):
            schema({"device_id": "dev-1", "body": 3, "feet": 3, "timer": "5 hours"})

    def test_missing_device_id_rejects(self, schema):
        """Missing device_id should be rejected."""
        with pytest.raises(vol.Invalid):
            schema({"body": 3, "feet": 3})

    def test_missing_body_rejects(self, schema):
        """Missing body should be rejected."""
        with pytest.raises(vol.Invalid):
            schema({"device_id": "dev-1", "feet": 3})

    def test_missing_feet_rejects(self, schema):
        """Missing feet should be rejected."""
        with pytest.raises(vol.Invalid):
            schema({"device_id": "dev-1", "body": 3})

    def test_all_timer_options_accepted(self, schema):
        """Every key in TIMER_OPTIONS should be a valid timer value."""
        for label in TIMER_OPTIONS:
            result = schema(
                {"device_id": "dev-1", "body": 1, "feet": 1, "timer": label}
            )
            assert result["timer"] == label


class TestPlatforms:
    """Test platform configuration."""

    def test_platforms_include_select_sensor_button(self):
        """Integration should forward to select, sensor, and button platforms."""
        from homeassistant.const import Platform

        assert Platform.SELECT in PLATFORMS
        assert Platform.SENSOR in PLATFORMS
        assert Platform.BUTTON in PLATFORMS
        assert len(PLATFORMS) == 3
