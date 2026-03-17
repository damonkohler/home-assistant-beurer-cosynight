"""Tests for the Beurer CosyNight config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.data_entry_flow import AbortFlow

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


def _make_reauth_flow(mock_hass, *, username="test@example.com", password="old_pass"):
    """Create a config flow in reauth mode with a mock existing entry."""
    entry = MagicMock()
    entry.entry_id = "existing_entry_id"
    entry.data = {"username": username, "password": password}
    entry.unique_id = username
    entry.title = f"Beurer CosyNight ({username})"

    mock_hass.config_entries.async_get_known_entry = MagicMock(return_value=entry)

    flow = BeurerCosyNightConfigFlow()
    flow.hass = mock_hass
    flow.context = {
        "source": "reauth",
        "entry_id": entry.entry_id,
        "unique_id": username,
    }

    return flow, entry


@pytest.fixture
def reauth_flow(mock_hass):
    """Return a config flow in reauth mode with a mock existing entry."""
    flow, entry = _make_reauth_flow(mock_hass)
    return flow


class TestConfigFlowUserStep:
    """Test the user step of the config flow."""

    async def test_show_form_when_no_input(self, flow):
        """No user_input shows the form."""
        result = await flow.async_step_user(user_input=None)

        assert result["type"] == "form"
        assert result["step_id"] == "user"
        assert result["errors"] == {}

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

    async def test_unexpected_exception_maps_to_unknown(self, flow):
        """Unexpected exceptions should show unknown error."""
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
        assert result["errors"] == {"base": "unknown"}

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


class TestConfigFlowReauth:
    """Test the reauth flow."""

    async def test_reauth_shows_confirm_form(self, reauth_flow):
        """async_step_reauth should show the reauth_confirm form."""
        result = await reauth_flow.async_step_reauth(
            entry_data={"username": "test@example.com", "password": "old_pass"}
        )

        assert result["type"] == "form"
        assert result["step_id"] == "reauth_confirm"
        assert result["errors"] == {}

    async def test_reauth_confirm_shows_form_when_no_input(self, reauth_flow):
        """No user_input shows the reauth_confirm form."""
        result = await reauth_flow.async_step_reauth_confirm(user_input=None)

        assert result["type"] == "form"
        assert result["step_id"] == "reauth_confirm"
        assert result["errors"] == {}

    async def test_reauth_confirm_prefills_username(self, reauth_flow):
        """The reauth_confirm form should pre-fill the username."""
        result = await reauth_flow.async_step_reauth_confirm(user_input=None)

        # Check that the schema has the username defaulted to existing value
        schema = result["data_schema"]
        for key in schema.schema:
            if key == "username":
                assert key.default() == "test@example.com"
                break
        else:
            pytest.fail("username field not found in schema")

    async def test_reauth_confirm_success(self, mock_hass):
        """Valid credentials update the entry and abort with reauth_successful."""
        flow, entry = _make_reauth_flow(mock_hass)

        with patch(
            "custom_components.beurer_cosynight.config_flow.BeurerCosyNight"
        ) as MockHub:
            MockHub.return_value.authenticate = AsyncMock(return_value=None)
            with (
                patch.object(flow, "async_set_unique_id", new_callable=AsyncMock),
                patch.object(flow, "_abort_if_unique_id_mismatch"),
                patch.object(flow, "async_update_reload_and_abort") as mock_update,
            ):
                mock_update.return_value = {
                    "type": "abort",
                    "reason": "reauth_successful",
                }
                await flow.async_step_reauth_confirm(
                    user_input={
                        "username": "test@example.com",
                        "password": "new_pass123",
                    }
                )

        mock_update.assert_called_once_with(
            entry,
            data={
                "username": "test@example.com",
                "password": "new_pass123",
            },
        )

    async def test_reauth_confirm_invalid_credentials(self, reauth_flow):
        """Invalid credentials should show the form again with error."""
        with patch(
            "custom_components.beurer_cosynight.config_flow.BeurerCosyNight"
        ) as MockHub:
            MockHub.return_value.authenticate = AsyncMock(
                side_effect=AuthError("bad creds")
            )
            result = await reauth_flow.async_step_reauth_confirm(
                user_input={
                    "username": "test@example.com",
                    "password": "wrong_password",
                }
            )

        assert result["type"] == "form"
        assert result["step_id"] == "reauth_confirm"
        assert result["errors"] == {"base": "invalid_auth"}

    async def test_reauth_confirm_api_error(self, reauth_flow):
        """ApiError should show the form again with cannot_connect error."""
        with patch(
            "custom_components.beurer_cosynight.config_flow.BeurerCosyNight"
        ) as MockHub:
            MockHub.return_value.authenticate = AsyncMock(
                side_effect=ApiError("connection failed")
            )
            result = await reauth_flow.async_step_reauth_confirm(
                user_input={
                    "username": "test@example.com",
                    "password": "some_password",
                }
            )

        assert result["type"] == "form"
        assert result["step_id"] == "reauth_confirm"
        assert result["errors"] == {"base": "cannot_connect"}

    async def test_reauth_confirm_unexpected_error(self, reauth_flow):
        """Unexpected exceptions should show the form with unknown error."""
        with patch(
            "custom_components.beurer_cosynight.config_flow.BeurerCosyNight"
        ) as MockHub:
            MockHub.return_value.authenticate = AsyncMock(
                side_effect=RuntimeError("something weird")
            )
            result = await reauth_flow.async_step_reauth_confirm(
                user_input={
                    "username": "test@example.com",
                    "password": "some_password",
                }
            )

        assert result["type"] == "form"
        assert result["step_id"] == "reauth_confirm"
        assert result["errors"] == {"base": "unknown"}

    async def test_reauth_confirm_shows_description_placeholders(self, reauth_flow):
        """The reauth form should include description_placeholders with name."""
        result = await reauth_flow.async_step_reauth_confirm(user_input=None)

        assert "description_placeholders" in result
        assert (
            result["description_placeholders"]["name"]
            == "Beurer CosyNight (test@example.com)"
        )

    async def test_reauth_confirm_wrong_account_aborts(self, mock_hass):
        """Entering credentials for a different account should abort."""
        flow, entry = _make_reauth_flow(
            mock_hass, username="original@example.com", password="old_pass"
        )

        with patch(
            "custom_components.beurer_cosynight.config_flow.BeurerCosyNight"
        ) as MockHub:
            MockHub.return_value.authenticate = AsyncMock(return_value=None)

            async def _set_unique_id(uid, **kwargs):
                flow.context["unique_id"] = uid

            with patch.object(flow, "async_set_unique_id", side_effect=_set_unique_id):
                with pytest.raises(AbortFlow, match="unique_id_mismatch"):
                    await flow.async_step_reauth_confirm(
                        user_input={
                            "username": "different@example.com",
                            "password": "some_password",
                        }
                    )
