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
)
from custom_components.beurer_cosynight.const import (
    DOMAIN,
    SECONDS_PER_MINUTE,
    TIMER_DEFAULT_MINUTES,
    TIMER_MAX_MINUTES,
    TIMER_MIN_MINUTES,
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

    async def test_setup_with_no_devices_logs_warning(
        self, mock_hass, mock_entry, mock_hub_async
    ):
        """Empty device list should log a warning and still succeed."""
        mock_hub_async.list_devices.return_value = []

        with (
            patch(
                "custom_components.beurer_cosynight.BeurerCosyNight",
                return_value=mock_hub_async,
            ),
            patch("custom_components.beurer_cosynight._LOGGER") as mock_logger,
        ):
            result = await async_setup_entry(mock_hass, mock_entry)

        assert result is True
        mock_logger.warning.assert_called_once_with("No Beurer CosyNight devices found")

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
        coord.execute_quickstart = AsyncMock()
        return coord

    @pytest.fixture
    async def quickstart_setup(
        self,
        mock_hass,
        mock_entry,
        mock_hub_async,
        coordinator,
        mock_device_registry,
    ):
        """Set up the integration and return the handler for tests.

        The dr.async_get patch must remain active when the handler is
        called (not just during setup), because the handler resolves
        the device registry at call time via dr.async_get(hass).
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

    async def test_happy_path_delegates_to_execute_quickstart(
        self, quickstart_handler, coordinator
    ):
        """Valid call should delegate to coordinator.execute_quickstart."""
        call = self._make_call(device_id=HA_DEVICE_ID, body=7, feet=3, timer=120)
        await quickstart_handler(call)

        coordinator.execute_quickstart.assert_awaited_once()
        qs = coordinator.execute_quickstart.call_args[0][0]
        assert isinstance(qs, Quickstart)
        assert qs.bodySetting == 7
        assert qs.feetSetting == 3
        assert qs.id == MOCK_DEVICE_ID
        assert qs.timespan == 7200  # 120 min * 60

    async def test_happy_path_does_not_call_refresh(
        self, quickstart_handler, coordinator
    ):
        """After quickstart, async_request_refresh should not be called."""
        call = self._make_call(device_id=HA_DEVICE_ID, body=5, feet=5)
        await quickstart_handler(call)

        coordinator.async_request_refresh.assert_not_called()

    async def test_default_timer_reads_from_entity(
        self, quickstart_handler, coordinator, mock_hass
    ):
        """Omitting timer should read from the TimerNumber entity.

        The entity defaults to TIMER_DEFAULT_MINUTES (60), so the
        timespan should be 3600 seconds.
        """
        call = self._make_call(device_id=HA_DEVICE_ID, body=5, feet=5)
        await quickstart_handler(call)

        qs = coordinator.execute_quickstart.call_args[0][0]
        assert qs.timespan == TIMER_DEFAULT_MINUTES * SECONDS_PER_MINUTE

    async def test_default_timer_reads_custom_entity_value(
        self, quickstart_handler, coordinator, mock_hass
    ):
        """When timer is omitted but entity value was changed, use entity value.

        Modify the TimerNumber entity in hass.data to 90 minutes, then
        verify the service handler reads 90 * 60 = 5400.
        """
        # Find the timer entity stored in hass.data and change its value.
        for entry_data in mock_hass.data[DOMAIN].values():
            timers = entry_data.get("timers", {})
            timer = timers.get(MOCK_DEVICE_ID)
            if timer is not None:
                timer._attr_native_value = 90.0
                break

        call = self._make_call(device_id=HA_DEVICE_ID, body=5, feet=5)
        await quickstart_handler(call)

        qs = coordinator.execute_quickstart.call_args[0][0]
        assert qs.timespan == 5400  # 90 min * 60

    async def test_explicit_timer_overrides_entity(
        self, quickstart_handler, coordinator, mock_hass
    ):
        """Explicit timer param should override the entity value."""
        # Set entity to 90 minutes
        for entry_data in mock_hass.data[DOMAIN].values():
            timers = entry_data.get("timers", {})
            timer = timers.get(MOCK_DEVICE_ID)
            if timer is not None:
                timer._attr_native_value = 90.0
                break

        call = self._make_call(device_id=HA_DEVICE_ID, body=1, feet=1, timer=120)
        await quickstart_handler(call)

        qs = coordinator.execute_quickstart.call_args[0][0]
        assert qs.timespan == 7200  # 120 min * 60, not 90 * 60

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

        with pytest.raises(
            HomeAssistantError,
            match="not a Beurer CosyNight device",
        ):
            await quickstart_handler(call)

    async def test_no_coordinator_for_device_raises(
        self,
        mock_hass,
        mock_entry,
        mock_hub_async,
        mock_device_registry,
    ):
        """Device with Beurer identifier but no coordinator should raise.

        This can happen if the device belongs to a different config
        entry than the one that registered the coordinators.
        """
        coord = AsyncMock()
        coord.hub = mock_hub_async
        coord.quickstart_lock = asyncio.Lock()
        coord.execute_quickstart = AsyncMock()
        mock_hass.services.has_service.return_value = False

        # Keep dr.async_get patched for the handler invocation.
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
            await async_setup_entry(mock_hass, mock_entry)

            handler = mock_hass.services.async_register.call_args[0][2]

            # Return a Beurer device with a DIFFERENT id.
            other_entry = MagicMock()
            other_entry.identifiers = {(DOMAIN, "device-xyz-999")}
            mock_device_registry.async_get.return_value = other_entry

            call = MagicMock()
            call.data = {
                "device_id": HA_DEVICE_ID,
                "body": 5,
                "feet": 5,
            }

            with pytest.raises(HomeAssistantError, match="No coordinator"):
                await handler(call)

    async def test_auth_error_propagates(self, quickstart_handler, coordinator):
        """AuthError from execute_quickstart should propagate."""
        coordinator.execute_quickstart = AsyncMock(
            side_effect=HomeAssistantError("Authentication failed")
        )
        call = self._make_call(device_id=HA_DEVICE_ID, body=5, feet=5)
        with pytest.raises(HomeAssistantError, match="Authentication failed"):
            await quickstart_handler(call)

    async def test_api_error_propagates(self, quickstart_handler, coordinator):
        """ApiError from execute_quickstart should propagate."""
        coordinator.execute_quickstart = AsyncMock(
            side_effect=HomeAssistantError("API error: timeout")
        )
        call = self._make_call(device_id=HA_DEVICE_ID, body=5, feet=5)
        with pytest.raises(HomeAssistantError, match="API error"):
            await quickstart_handler(call)

    async def test_body_zero_and_feet_zero(self, quickstart_handler, coordinator):
        """Setting both zones to 0 should still send a valid quickstart."""
        call = self._make_call(device_id=HA_DEVICE_ID, body=0, feet=0)
        await quickstart_handler(call)

        qs = coordinator.execute_quickstart.call_args[0][0]
        assert qs.bodySetting == 0
        assert qs.feetSetting == 0

    async def test_body_max_and_feet_max(self, quickstart_handler, coordinator):
        """Maximum zone values (9) should be accepted."""
        call = self._make_call(device_id=HA_DEVICE_ID, body=9, feet=9)
        await quickstart_handler(call)

        qs = coordinator.execute_quickstart.call_args[0][0]
        assert qs.bodySetting == 9
        assert qs.feetSetting == 9


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
        """Timer field should accept integer minutes within range."""
        result = schema(
            {
                "device_id": "dev-1",
                "body": 5,
                "feet": 3,
                "timer": 120,
            }
        )
        assert result["timer"] == 120

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

    def test_invalid_timer_zero_rejects(self, schema):
        """Timer value 0 (below minimum 1) should be rejected."""
        with pytest.raises(vol.Invalid):
            schema(
                {
                    "device_id": "dev-1",
                    "body": 3,
                    "feet": 3,
                    "timer": 0,
                }
            )

    def test_invalid_timer_above_max_rejects(self, schema):
        """Timer value 241 (above maximum 240) should be rejected."""
        with pytest.raises(vol.Invalid):
            schema(
                {
                    "device_id": "dev-1",
                    "body": 3,
                    "feet": 3,
                    "timer": 241,
                }
            )

    def test_invalid_timer_negative_rejects(self, schema):
        """Negative timer value should be rejected."""
        with pytest.raises(vol.Invalid):
            schema(
                {
                    "device_id": "dev-1",
                    "body": 3,
                    "feet": 3,
                    "timer": -1,
                }
            )

    def test_invalid_timer_string_rejects(self, schema):
        """String timer value (old format) should be rejected."""
        with pytest.raises(vol.Invalid):
            schema(
                {
                    "device_id": "dev-1",
                    "body": 3,
                    "feet": 3,
                    "timer": "1 hour",
                }
            )

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

    def test_timer_min_boundary_accepted(self, schema):
        """Minimum timer value (1 minute) should be accepted."""
        result = schema(
            {
                "device_id": "dev-1",
                "body": 1,
                "feet": 1,
                "timer": TIMER_MIN_MINUTES,
            }
        )
        assert result["timer"] == TIMER_MIN_MINUTES

    def test_timer_default_accepted(self, schema):
        """Default timer value (60 minutes) should be accepted."""
        result = schema(
            {
                "device_id": "dev-1",
                "body": 1,
                "feet": 1,
                "timer": TIMER_DEFAULT_MINUTES,
            }
        )
        assert result["timer"] == TIMER_DEFAULT_MINUTES

    def test_timer_max_boundary_accepted(self, schema):
        """Maximum timer value (240 minutes) should be accepted."""
        result = schema(
            {
                "device_id": "dev-1",
                "body": 1,
                "feet": 1,
                "timer": TIMER_MAX_MINUTES,
            }
        )
        assert result["timer"] == TIMER_MAX_MINUTES

    def test_timer_coerced_from_string(self, schema):
        """String timer value that represents a valid int should be coerced."""
        result = schema(
            {
                "device_id": "dev-1",
                "body": 1,
                "feet": 1,
                "timer": "120",
            }
        )
        assert result["timer"] == 120


class TestPlatforms:
    """Test platform configuration."""

    def test_platforms_include_select_sensor_button_number(self):
        """Integration should forward to select, sensor, button, and number platforms."""
        from homeassistant.const import Platform

        assert Platform.SELECT in PLATFORMS
        assert Platform.SENSOR in PLATFORMS
        assert Platform.BUTTON in PLATFORMS
        assert Platform.NUMBER in PLATFORMS
        assert len(PLATFORMS) == 4
