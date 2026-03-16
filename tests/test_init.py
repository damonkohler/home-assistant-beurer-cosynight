"""Tests for Beurer CosyNight integration setup and unload."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from custom_components.beurer_cosynight import (
    PLATFORMS,
    async_setup_entry,
    async_unload_entry,
)
from custom_components.beurer_cosynight.beurer_cosynight import (
    ApiError,
    AuthError,
)

from .conftest import (
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


class TestAsyncSetupEntry:
    """Test async_setup_entry with async hub."""

    @pytest.mark.asyncio
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

    @pytest.mark.asyncio
    async def test_api_error_raises_config_entry_not_ready(self, mock_hass, mock_entry):
        """ApiError from hub should raise ConfigEntryNotReady."""
        with patch("custom_components.beurer_cosynight.BeurerCosyNight") as MockHub:
            MockHub.return_value.authenticate = AsyncMock(
                side_effect=ApiError("Connection failed")
            )
            with pytest.raises(ConfigEntryNotReady):
                await async_setup_entry(mock_hass, mock_entry)

    @pytest.mark.asyncio
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

    @pytest.mark.asyncio
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

    @pytest.mark.asyncio
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


class TestAsyncUnloadEntry:
    """Test async_unload_entry."""

    @pytest.mark.asyncio
    async def test_unload_removes_data(self, mock_hass):
        """Successful unload should remove entry data from hass.data."""
        from custom_components.beurer_cosynight.const import DOMAIN

        mock_entry = MagicMock()
        mock_entry.entry_id = "test_entry"
        mock_hass.data = {DOMAIN: {"test_entry": {"hub": MagicMock()}}}

        result = await async_unload_entry(mock_hass, mock_entry)

        assert result is True
        assert "test_entry" not in mock_hass.data[DOMAIN]

    @pytest.mark.asyncio
    async def test_unload_failure_keeps_data(self, mock_hass):
        """Failed unload should keep entry data."""
        from custom_components.beurer_cosynight.const import DOMAIN

        mock_entry = MagicMock()
        mock_entry.entry_id = "test_entry"
        mock_hass.data = {DOMAIN: {"test_entry": {"hub": MagicMock()}}}
        mock_hass.config_entries.async_unload_platforms = AsyncMock(return_value=False)

        result = await async_unload_entry(mock_hass, mock_entry)

        assert result is False
        assert "test_entry" in mock_hass.data[DOMAIN]


class TestPlatforms:
    """Test platform configuration."""

    def test_platforms_include_select_sensor_button(self):
        """Integration should forward to select, sensor, and button platforms."""
        from homeassistant.const import Platform

        assert Platform.SELECT in PLATFORMS
        assert Platform.SENSOR in PLATFORMS
        assert Platform.BUTTON in PLATFORMS
        assert len(PLATFORMS) == 3
