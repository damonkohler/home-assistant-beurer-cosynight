"""Tests for the Beurer CosyNight config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.beurer_cosynight.beurer_cosynight import ApiError, AuthError
from custom_components.beurer_cosynight.config_flow import BeurerCosyNightConfigFlow
from custom_components.beurer_cosynight.const import DOMAIN


@pytest.fixture(autouse=True)
def _patch_session():
    """Patch async_get_clientsession to avoid HA network stack in tests."""
    with patch(
        "custom_components.beurer_cosynight.config_flow.async_get_clientsession",
        return_value=MagicMock(),
    ):
        yield


@pytest.fixture
def flow(mock_hass):
    """Return a config flow instance with mock hass."""
    flow = BeurerCosyNightConfigFlow()
    flow.hass = mock_hass
    return flow


class TestConfigFlowUserStep:
    """Test the user step of the config flow."""

    @pytest.mark.asyncio
    async def test_show_form_when_no_input(self, flow):
        """No user_input shows the form."""
        result = await flow.async_step_user(user_input=None)

        assert result["type"] == "form"
        assert result["step_id"] == "user"
        assert result["errors"] == {}

    @pytest.mark.asyncio
    async def test_successful_auth_creates_entry(self, flow):
        """Successful authentication creates a config entry."""
        with patch(
            "custom_components.beurer_cosynight.config_flow.BeurerCosyNight"
        ) as MockHub:
            MockHub.return_value.authenticate = AsyncMock(return_value=None)
            with (
                patch.object(flow, "async_set_unique_id", new_callable=AsyncMock),
                patch.object(flow, "_abort_if_unique_id_configured"),
            ):
                result = await flow.async_step_user(
                    user_input={
                        "username": "test@example.com",
                        "password": "pass123",
                    }
                )

        assert result["type"] == "create_entry"
        assert result["title"] == "Beurer CosyNight (test@example.com)"
        assert result["data"] == {
            "username": "test@example.com",
            "password": "pass123",
        }

    @pytest.mark.asyncio
    async def test_auth_error_shows_invalid_auth(self, flow):
        """AuthError should map to invalid_auth error."""
        with patch(
            "custom_components.beurer_cosynight.config_flow.BeurerCosyNight"
        ) as MockHub:
            MockHub.return_value.authenticate = AsyncMock(
                side_effect=AuthError("bad creds")
            )
            result = await flow.async_step_user(
                user_input={"username": "bad@example.com", "password": "wrong"}
            )

        assert result["type"] == "form"
        assert result["errors"] == {"base": "invalid_auth"}

    @pytest.mark.asyncio
    async def test_api_error_shows_cannot_connect(self, flow):
        """ApiError should map to cannot_connect error."""
        with patch(
            "custom_components.beurer_cosynight.config_flow.BeurerCosyNight"
        ) as MockHub:
            MockHub.return_value.authenticate = AsyncMock(
                side_effect=ApiError("connection refused")
            )
            result = await flow.async_step_user(
                user_input={"username": "test@example.com", "password": "pass"}
            )

        assert result["type"] == "form"
        assert result["errors"] == {"base": "cannot_connect"}

    @pytest.mark.asyncio
    async def test_unexpected_exception_maps_to_cannot_connect(self, flow):
        """Unexpected exceptions should show cannot_connect."""
        with patch(
            "custom_components.beurer_cosynight.config_flow.BeurerCosyNight"
        ) as MockHub:
            MockHub.return_value.authenticate = AsyncMock(
                side_effect=RuntimeError("something weird")
            )
            result = await flow.async_step_user(
                user_input={"username": "test@example.com", "password": "pass"}
            )

        assert result["type"] == "form"
        assert result["errors"] == {"base": "cannot_connect"}

    @pytest.mark.asyncio
    async def test_authenticate_awaited_directly(self, flow):
        """Config flow should await authenticate directly, not via executor."""
        with patch(
            "custom_components.beurer_cosynight.config_flow.BeurerCosyNight"
        ) as MockHub:
            mock_hub = MockHub.return_value
            mock_hub.authenticate = AsyncMock(return_value=None)

            with (
                patch.object(flow, "async_set_unique_id", new_callable=AsyncMock),
                patch.object(flow, "_abort_if_unique_id_configured"),
            ):
                await flow.async_step_user(
                    user_input={
                        "username": "test@example.com",
                        "password": "pass123",
                    }
                )

        mock_hub.authenticate.assert_awaited_once()


class TestFlowMetadata:
    """Test config flow class metadata."""

    def test_domain(self):
        """Config flow should be registered for the correct domain."""
        from homeassistant.config_entries import HANDLERS

        assert DOMAIN in HANDLERS

    def test_version(self):
        """Config flow version should be 1."""
        assert BeurerCosyNightConfigFlow.VERSION == 1
