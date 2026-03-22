"""Tests for the async BeurerCosyNight API client."""

from __future__ import annotations

import asyncio
import json
import os

import pytest

from custom_components.beurer_cosynight.beurer_cosynight import AuthError
from tests.conftest import FakeHttpClient

# Token response as the API returns it (with dotted keys)
TOKEN_RESPONSE = {
    "access_token": "test-access-token",
    ".expires": "Mon, 01 Jan 2099 00:00:00 GMT",
    ".issued": "Mon, 01 Jan 2024 00:00:00 GMT",
    "expires_in": 86400,
    "refresh_token": "test-refresh-token",
    "token_type": "Bearer",
    "user_email": "test@example.com",
    "user_id": "user-123",
}

EXPIRED_TOKEN = {
    "access_token": "expired-access-token",
    "expires": "Mon, 01 Jan 2020 00:00:00 GMT",
    "issued": "Mon, 01 Jan 2019 00:00:00 GMT",
    "expires_in": 86400,
    "refresh_token": "old-refresh-token",
    "token_type": "Bearer",
    "user_email": "test@example.com",
    "user_id": "user-123",
}

VALID_TOKEN = {
    "access_token": "valid-access-token",
    "expires": "Mon, 01 Jan 2099 00:00:00 GMT",
    "issued": "Mon, 01 Jan 2024 00:00:00 GMT",
    "expires_in": 86400,
    "refresh_token": "valid-refresh-token",
    "token_type": "Bearer",
    "user_email": "test@example.com",
    "user_id": "user-123",
}

STATUS_RESPONSE = {
    "active": True,
    "bodySetting": 3,
    "feetSetting": 5,
    "heartbeat": 100,
    "id": "device-123",
    "name": "My Pad",
    "requieresUpdate": False,
    "timer": 1800,
}

LIST_DEVICES_RESPONSE = {
    "devices": [
        {
            "active": True,
            "id": "device-123",
            "name": "My Pad",
            "requieresUpdate": False,
        }
    ]
}


class TestAsyncConstructor:
    """Test BeurerCosyNight constructor with HttpClient DI."""

    def test_constructor_takes_http_client_as_first_arg(self):
        """Constructor's first positional arg should be an HttpClient."""
        from custom_components.beurer_cosynight.beurer_cosynight import BeurerCosyNight

        client = FakeHttpClient()
        hub = BeurerCosyNight(client, token_path="/dev/null")
        assert hub._client is client

    def test_constructor_with_all_params(self):
        """Constructor should accept client, token_path, username, password."""
        from custom_components.beurer_cosynight.beurer_cosynight import BeurerCosyNight

        client = FakeHttpClient()
        hub = BeurerCosyNight(
            client, token_path="/dev/null", username="u", password="p"
        )
        assert hub._client is client
        assert hub._username == "u"
        assert hub._password == "p"

    def test_constructor_does_not_do_file_io(self, tmp_path):
        """Constructor should NOT do file I/O — deferred to authenticate()."""
        from custom_components.beurer_cosynight.beurer_cosynight import BeurerCosyNight

        client = FakeHttpClient()
        token_path = str(tmp_path / "nonexistent_token")
        hub = BeurerCosyNight(client, token_path=token_path)
        assert hub._token is None


class TestAsyncAuthenticate:
    """Test async authenticate method."""

    async def test_authenticate_is_async(self, tmp_path):
        """authenticate() should be a coroutine."""
        from custom_components.beurer_cosynight.beurer_cosynight import BeurerCosyNight

        client = FakeHttpClient([TOKEN_RESPONSE])
        hub = BeurerCosyNight(client, token_path=str(tmp_path / "token"))
        result = hub.authenticate("u", "p")
        assert asyncio.iscoroutine(result)
        await result

    async def test_authenticate_with_password(self, tmp_path):
        """Successful password authentication should set token."""
        from custom_components.beurer_cosynight.beurer_cosynight import BeurerCosyNight

        client = FakeHttpClient([TOKEN_RESPONSE])
        hub = BeurerCosyNight(client, token_path=str(tmp_path / "token"))
        await hub.authenticate("user@test.com", "pass123")
        assert hub._token is not None
        assert hub._token.access_token == "test-access-token"

    async def test_authenticate_sends_password_grant(self, tmp_path):
        """authenticate() should POST with grant_type=password."""
        from custom_components.beurer_cosynight.beurer_cosynight import BeurerCosyNight

        client = FakeHttpClient([TOKEN_RESPONSE])
        hub = BeurerCosyNight(client, token_path=str(tmp_path / "token"))
        await hub.authenticate("user@test.com", "pass123")

        assert len(client.requests) >= 1
        method, url, kwargs = client.requests[0]
        assert method == "POST"
        assert "/token" in url
        assert kwargs["data"]["grant_type"] == "password"
        assert kwargs["data"]["username"] == "user@test.com"
        assert kwargs["data"]["password"] == "pass123"

    async def test_authenticate_stores_credentials(self, tmp_path):
        """authenticate() should store credentials for future re-auth."""
        from custom_components.beurer_cosynight.beurer_cosynight import BeurerCosyNight

        client = FakeHttpClient([TOKEN_RESPONSE])
        hub = BeurerCosyNight(client, token_path=str(tmp_path / "token"))
        await hub.authenticate("user@test.com", "mypass")
        assert hub._username == "user@test.com"
        assert hub._password == "mypass"

    async def test_authenticate_auth_error_on_401(self, tmp_path):
        """AuthError from HttpClient should propagate."""
        from custom_components.beurer_cosynight.beurer_cosynight import (
            AuthError,
            BeurerCosyNight,
        )

        client = FakeHttpClient()
        client.add_error(AuthError("401 Unauthorized"))
        hub = BeurerCosyNight(client, token_path=str(tmp_path / "token"))
        with pytest.raises(AuthError):
            await hub.authenticate("u", "p")

    async def test_authenticate_api_error_on_network_failure(self, tmp_path):
        """ApiError from HttpClient should propagate."""
        from custom_components.beurer_cosynight.beurer_cosynight import (
            ApiError,
            BeurerCosyNight,
        )

        client = FakeHttpClient()
        client.add_error(ApiError("Connection refused"))
        hub = BeurerCosyNight(client, token_path=str(tmp_path / "token"))
        with pytest.raises(ApiError):
            await hub.authenticate("u", "p")


class TestAsyncTokenPersistence:
    """Test token loading/saving uses asyncio.to_thread for file I/O."""

    async def test_load_token_from_disk(self, tmp_path):
        """Valid token on disk should be loaded during authenticate."""
        from custom_components.beurer_cosynight.beurer_cosynight import BeurerCosyNight

        token_path = str(tmp_path / "token")
        with open(token_path, "w") as f:
            json.dump(VALID_TOKEN, f)

        client = FakeHttpClient()
        hub = BeurerCosyNight(client, token_path=token_path, username="u", password="p")
        await hub.authenticate("u", "p")

        assert hub._token is not None
        assert hub._token.access_token == "valid-access-token"
        # No HTTP requests needed since token is valid
        assert len(client.requests) == 0

    async def test_save_token_to_disk(self, tmp_path):
        """Token should be saved to disk after authentication."""
        from custom_components.beurer_cosynight.beurer_cosynight import BeurerCosyNight

        token_path = str(tmp_path / "storage" / "token")
        client = FakeHttpClient([TOKEN_RESPONSE])
        hub = BeurerCosyNight(client, token_path=token_path)
        await hub.authenticate("u", "p")

        assert os.path.exists(token_path)
        with open(token_path) as f:
            saved = json.load(f)
        assert saved["access_token"] == "test-access-token"

    async def test_corrupt_token_falls_back_to_password(self, tmp_path):
        """Corrupt token file should trigger fallback to password auth."""
        from custom_components.beurer_cosynight.beurer_cosynight import BeurerCosyNight

        token_path = str(tmp_path / "token")
        with open(token_path, "w") as f:
            f.write("not valid json {{{")

        client = FakeHttpClient([TOKEN_RESPONSE])
        hub = BeurerCosyNight(client, token_path=token_path, username="u", password="p")
        await hub.authenticate("u", "p")
        assert hub._token.access_token == "test-access-token"


class TestAsyncTokenRefresh:
    """Test async token refresh logic."""

    async def test_refresh_expired_token(self, tmp_path):
        """Expired token should be refreshed via POST."""
        from custom_components.beurer_cosynight.beurer_cosynight import BeurerCosyNight

        token_path = str(tmp_path / "token")
        with open(token_path, "w") as f:
            json.dump(EXPIRED_TOKEN, f)

        client = FakeHttpClient([TOKEN_RESPONSE])
        hub = BeurerCosyNight(client, token_path=token_path, username="u", password="p")
        await hub.authenticate("u", "p")
        assert hub._token.access_token == "test-access-token"

    async def test_refresh_failure_falls_back_to_reauth(self, tmp_path):
        """Failed refresh with stored credentials should re-authenticate."""
        from custom_components.beurer_cosynight.beurer_cosynight import (
            AuthError,
            BeurerCosyNight,
        )

        token_path = str(tmp_path / "token")
        with open(token_path, "w") as f:
            json.dump(EXPIRED_TOKEN, f)

        # First response: refresh fails, second: password auth succeeds
        client = FakeHttpClient()
        client.add_error(AuthError("refresh failed"))
        client.add_response(TOKEN_RESPONSE)

        hub = BeurerCosyNight(client, token_path=token_path, username="u", password="p")
        await hub.authenticate("u", "p")
        assert hub._token.access_token == "test-access-token"

    async def test_valid_token_not_refreshed(self, tmp_path):
        """Valid (non-expired) token should not trigger any HTTP requests."""
        from custom_components.beurer_cosynight.beurer_cosynight import BeurerCosyNight

        token_path = str(tmp_path / "token")
        with open(token_path, "w") as f:
            json.dump(VALID_TOKEN, f)

        client = FakeHttpClient()
        hub = BeurerCosyNight(client, token_path=token_path, username="u", password="p")
        await hub.authenticate("u", "p")

        assert hub._token.access_token == "valid-access-token"
        assert len(client.requests) == 0


class TestAsyncTokenRefreshLock:
    """Test asyncio.Lock prevents concurrent token refresh (architect F2)."""

    async def test_concurrent_refresh_only_refreshes_once(self, tmp_path):
        """Two concurrent calls with expired token should only refresh once."""
        from custom_components.beurer_cosynight.beurer_cosynight import (
            BeurerCosyNight,
            _Token,
        )

        token_path = str(tmp_path / "token")
        # Queue: one refresh, two get_status responses
        client = FakeHttpClient(
            [
                TOKEN_RESPONSE,  # refresh token
                STATUS_RESPONSE,  # get_status #1
                STATUS_RESPONSE,  # get_status #2
            ]
        )
        hub = BeurerCosyNight(client, token_path=token_path, username="u", password="p")
        # Set an expired token directly
        hub._token = _Token(**EXPIRED_TOKEN)

        # Run two get_status calls concurrently — both detect expired token,
        # but the lock should ensure only one actual refresh happens
        _results = await asyncio.gather(
            hub.get_status("device-1"),
            hub.get_status("device-2"),
        )

        # Count how many POST requests went to /token (refresh)
        token_posts = [
            r for r in client.requests if "/token" in r[1] and r[0] == "POST"
        ]
        assert len(token_posts) == 1, f"Expected 1 refresh, got {len(token_posts)}"


class TestAsyncGetStatus:
    """Test async get_status method."""

    async def test_get_status_is_async(self):
        """get_status() should be a coroutine."""
        from custom_components.beurer_cosynight.beurer_cosynight import (
            BeurerCosyNight,
            _Token,
        )

        client = FakeHttpClient([STATUS_RESPONSE])
        hub = BeurerCosyNight(client, token_path="/dev/null")
        hub._token = _Token(**VALID_TOKEN)
        result = hub.get_status("device-123")
        assert asyncio.iscoroutine(result)
        await result

    async def test_get_status_returns_status(self):
        """get_status should return a Status dataclass."""
        from custom_components.beurer_cosynight.beurer_cosynight import (
            BeurerCosyNight,
            Status,
            _Token,
        )

        client = FakeHttpClient([STATUS_RESPONSE])
        hub = BeurerCosyNight(client, token_path="/dev/null")
        hub._token = _Token(**VALID_TOKEN)
        status = await hub.get_status("device-123")

        assert isinstance(status, Status)
        assert status.bodySetting == 3
        assert status.feetSetting == 5
        assert status.timer == 1800
        assert status.requiresUpdate is False

    async def test_get_status_sends_device_id_as_json(self):
        """get_status should POST with device ID in JSON body."""
        from custom_components.beurer_cosynight.beurer_cosynight import (
            BeurerCosyNight,
            _Token,
        )

        client = FakeHttpClient([STATUS_RESPONSE])
        hub = BeurerCosyNight(client, token_path="/dev/null")
        hub._token = _Token(**VALID_TOKEN)
        await hub.get_status("device-123")

        status_posts = [r for r in client.requests if "GetStatus" in r[1]]
        assert len(status_posts) == 1
        assert status_posts[0][2]["json"] == {"id": "device-123"}

    async def test_get_status_uses_auth_header(self):
        """get_status should include Bearer token in Authorization header."""
        from custom_components.beurer_cosynight.beurer_cosynight import (
            BeurerCosyNight,
            _Token,
        )

        client = FakeHttpClient([STATUS_RESPONSE])
        hub = BeurerCosyNight(client, token_path="/dev/null")
        hub._token = _Token(**VALID_TOKEN)
        await hub.get_status("device-123")

        status_posts = [r for r in client.requests if "GetStatus" in r[1]]
        headers = status_posts[0][2]["headers"]
        assert headers["Authorization"] == "Bearer valid-access-token"

    async def test_get_status_auth_error(self):
        """AuthError from HttpClient should propagate from get_status."""
        from custom_components.beurer_cosynight.beurer_cosynight import (
            AuthError,
            BeurerCosyNight,
            _Token,
        )

        client = FakeHttpClient()
        client.add_error(AuthError("401"))
        hub = BeurerCosyNight(client, token_path="/dev/null")
        hub._token = _Token(**VALID_TOKEN)
        with pytest.raises(AuthError):
            await hub.get_status("device-123")

    async def test_get_status_api_error(self):
        """ApiError from HttpClient should propagate from get_status."""
        from custom_components.beurer_cosynight.beurer_cosynight import (
            ApiError,
            BeurerCosyNight,
            _Token,
        )

        client = FakeHttpClient()
        client.add_error(ApiError("500 Server Error"))
        hub = BeurerCosyNight(client, token_path="/dev/null")
        hub._token = _Token(**VALID_TOKEN)
        with pytest.raises(ApiError):
            await hub.get_status("device-123")


class TestAsyncListDevices:
    """Test async list_devices method."""

    async def test_list_devices_is_async(self):
        """list_devices() should be a coroutine."""
        from custom_components.beurer_cosynight.beurer_cosynight import (
            BeurerCosyNight,
            _Token,
        )

        client = FakeHttpClient([LIST_DEVICES_RESPONSE])
        hub = BeurerCosyNight(client, token_path="/dev/null")
        hub._token = _Token(**VALID_TOKEN)
        result = hub.list_devices()
        assert asyncio.iscoroutine(result)
        await result

    async def test_list_devices_returns_device_objects(self):
        """list_devices should return a list of Device dataclasses."""
        from custom_components.beurer_cosynight.beurer_cosynight import (
            BeurerCosyNight,
            Device,
            _Token,
        )

        client = FakeHttpClient([LIST_DEVICES_RESPONSE])
        hub = BeurerCosyNight(client, token_path="/dev/null")
        hub._token = _Token(**VALID_TOKEN)
        devices = await hub.list_devices()

        assert len(devices) == 1
        assert isinstance(devices[0], Device)
        assert devices[0].id == "device-123"
        assert devices[0].name == "My Pad"

    async def test_list_devices_empty(self):
        """Empty device list should return empty list."""
        from custom_components.beurer_cosynight.beurer_cosynight import (
            BeurerCosyNight,
            _Token,
        )

        client = FakeHttpClient([{"devices": []}])
        hub = BeurerCosyNight(client, token_path="/dev/null")
        hub._token = _Token(**VALID_TOKEN)
        devices = await hub.list_devices()
        assert devices == []

    async def test_list_devices_uses_get_method(self):
        """list_devices should use GET, not POST."""
        from custom_components.beurer_cosynight.beurer_cosynight import (
            BeurerCosyNight,
            _Token,
        )

        client = FakeHttpClient([LIST_DEVICES_RESPONSE])
        hub = BeurerCosyNight(client, token_path="/dev/null")
        hub._token = _Token(**VALID_TOKEN)
        await hub.list_devices()

        list_reqs = [r for r in client.requests if "Device/List" in r[1]]
        assert len(list_reqs) == 1
        assert list_reqs[0][0] == "GET"


class TestAsyncQuickstart:
    """Test async quickstart method."""

    async def test_quickstart_is_async(self):
        """quickstart() should be a coroutine."""
        from custom_components.beurer_cosynight.beurer_cosynight import (
            BeurerCosyNight,
            Quickstart,
            _Token,
        )

        client = FakeHttpClient([{}])
        hub = BeurerCosyNight(client, token_path="/dev/null")
        hub._token = _Token(**VALID_TOKEN)
        qs = Quickstart(bodySetting=3, feetSetting=5, id="d1", timespan=3600)
        result = hub.quickstart(qs)
        assert asyncio.iscoroutine(result)
        await result

    async def test_quickstart_sends_correct_payload(self):
        """quickstart should POST all Quickstart fields as JSON."""
        from custom_components.beurer_cosynight.beurer_cosynight import (
            BeurerCosyNight,
            Quickstart,
            _Token,
        )

        client = FakeHttpClient([{}])
        hub = BeurerCosyNight(client, token_path="/dev/null")
        hub._token = _Token(**VALID_TOKEN)
        qs = Quickstart(bodySetting=3, feetSetting=5, id="device-123", timespan=3600)
        await hub.quickstart(qs)

        qs_posts = [r for r in client.requests if "Quickstart" in r[1]]
        assert len(qs_posts) == 1
        assert qs_posts[0][2]["json"] == {
            "bodySetting": 3,
            "feetSetting": 5,
            "id": "device-123",
            "timespan": 3600,
        }

    async def test_quickstart_stop_device(self):
        """quickstart with all zeros should stop the device."""
        from custom_components.beurer_cosynight.beurer_cosynight import (
            BeurerCosyNight,
            Quickstart,
            _Token,
        )

        client = FakeHttpClient([{}])
        hub = BeurerCosyNight(client, token_path="/dev/null")
        hub._token = _Token(**VALID_TOKEN)
        qs = Quickstart(bodySetting=0, feetSetting=0, id="device-123", timespan=0)
        await hub.quickstart(qs)

        payload = client.requests[-1][2]["json"]
        assert payload["bodySetting"] == 0
        assert payload["feetSetting"] == 0
        assert payload["timespan"] == 0


class TestAsyncErrorHierarchy:
    """Test the new error types exist and have correct hierarchy."""

    def test_base_error_exists(self):
        """BeurerCosyNightError should exist and be an Exception subclass."""
        from custom_components.beurer_cosynight.beurer_cosynight import (
            BeurerCosyNightError,
        )

        assert issubclass(BeurerCosyNightError, Exception)

    def test_auth_error_is_subclass_of_base(self):
        """AuthError should be a BeurerCosyNightError."""
        from custom_components.beurer_cosynight.beurer_cosynight import (
            AuthError,
            BeurerCosyNightError,
        )

        assert issubclass(AuthError, BeurerCosyNightError)

    def test_api_error_is_subclass_of_base(self):
        """ApiError should be a BeurerCosyNightError."""
        from custom_components.beurer_cosynight.beurer_cosynight import (
            ApiError,
            BeurerCosyNightError,
        )

        assert issubclass(ApiError, BeurerCosyNightError)

    def test_auth_error_is_not_api_error(self):
        """AuthError and ApiError should be separate branches."""
        from custom_components.beurer_cosynight.beurer_cosynight import (
            ApiError,
            AuthError,
        )

        assert not issubclass(AuthError, ApiError)

    def test_api_error_is_not_auth_error(self):
        """ApiError should not be a subclass of AuthError."""
        from custom_components.beurer_cosynight.beurer_cosynight import (
            ApiError,
            AuthError,
        )

        assert not issubclass(ApiError, AuthError)


class TestAsyncTokenPersistenceEdgeCases:
    """Edge cases for token loading and saving — restored from sync tests."""

    async def test_load_token_missing_fields(self, tmp_path):
        """Token file with missing fields should be handled gracefully."""
        from custom_components.beurer_cosynight.beurer_cosynight import BeurerCosyNight

        token_path = str(tmp_path / "token")
        with open(token_path, "w") as f:
            json.dump({"access_token": "only"}, f)

        client = FakeHttpClient([TOKEN_RESPONSE])
        hub = BeurerCosyNight(client, token_path=token_path, username="u", password="p")
        await hub.authenticate("u", "p")
        # Should fall back to password auth
        assert hub._token.access_token == "test-access-token"

    async def test_save_token_permission_error(self):
        """Failed token persistence should not raise."""
        from custom_components.beurer_cosynight.beurer_cosynight import BeurerCosyNight

        # Use a path that can't be written to
        token_path = "/nonexistent_root_dir/token"
        client = FakeHttpClient([TOKEN_RESPONSE])
        hub = BeurerCosyNight(client, token_path=token_path, username="u", password="p")
        # Should not raise even though token can't be saved
        await hub.authenticate("u", "p")
        assert hub._token.access_token == "test-access-token"

    def test_default_token_path(self):
        """Default token path should be 'token'."""
        from custom_components.beurer_cosynight.beurer_cosynight import BeurerCosyNight

        client = FakeHttpClient()
        hub = BeurerCosyNight(client)
        assert hub._token_path == "token"


class TestAsyncTokenRefreshEdgeCases:
    """Edge cases for token refresh — restored from sync tests."""

    async def test_no_token_no_credentials_raises(self):
        """No token and no credentials should raise."""
        from custom_components.beurer_cosynight.beurer_cosynight import BeurerCosyNight

        client = FakeHttpClient()
        hub = BeurerCosyNight(client)
        with pytest.raises(AuthError, match="Not authenticated"):
            await hub._refresh_token()

    async def test_no_token_with_credentials_authenticates(self, tmp_path):
        """No token but with credentials should do full auth."""
        from custom_components.beurer_cosynight.beurer_cosynight import BeurerCosyNight

        client = FakeHttpClient([TOKEN_RESPONSE])
        hub = BeurerCosyNight(
            client, token_path=str(tmp_path / "token"), username="u", password="p"
        )
        await hub._refresh_token()
        assert hub._token.access_token == "test-access-token"

    async def test_token_cleared_when_refresh_and_reauth_both_fail(self):
        """After refresh + re-auth failure (with retries), token must be None."""
        from unittest.mock import patch

        from custom_components.beurer_cosynight.beurer_cosynight import (
            AuthError,
            BeurerCosyNight,
            _Token,
        )

        client = FakeHttpClient()
        client.add_error(AuthError("refresh failed"))
        # 3 password auth attempts (initial + 2 retries)
        client.add_error(AuthError("reauth failed 1"))
        client.add_error(AuthError("reauth failed 2"))
        client.add_error(AuthError("reauth failed 3"))
        hub = BeurerCosyNight(client, username="u", password="p")
        hub._token = _Token(**EXPIRED_TOKEN)

        with patch("custom_components.beurer_cosynight.beurer_cosynight.asyncio.sleep"):
            with pytest.raises(AuthError):
                await hub._refresh_token()
        assert hub._token is None

    async def test_token_cleared_when_refresh_fails_no_credentials(self):
        """After refresh failure without credentials, token must be None."""
        from custom_components.beurer_cosynight.beurer_cosynight import (
            AuthError,
            BeurerCosyNight,
            _Token,
        )

        client = FakeHttpClient()
        client.add_error(AuthError("refresh failed"))
        hub = BeurerCosyNight(client)
        hub._token = _Token(**EXPIRED_TOKEN)

        with pytest.raises(AuthError):
            await hub._refresh_token()
        assert hub._token is None

    async def test_token_before_refresh_threshold_not_refreshed(self, tmp_path):
        """Token before 80% lifetime should NOT be refreshed."""
        import datetime
        from unittest.mock import patch

        from custom_components.beurer_cosynight.beurer_cosynight import (
            BeurerCosyNight,
            _Token,
        )

        hub = BeurerCosyNight(
            FakeHttpClient(),
            token_path=str(tmp_path / "token"),
            username="u",
            password="p",
        )
        # 12-hour token: issued at 00:00, expires at 12:00
        hub._token = _Token(
            access_token="boundary-token",
            expires="Wed, 15 Jan 2025 12:00:00 GMT",
            issued="Wed, 15 Jan 2025 00:00:00 GMT",
            expires_in=43200,
            refresh_token="boundary-refresh",
            token_type="Bearer",
            user_email="test@example.com",
            user_id="user-123",
        )

        # At 79% of lifetime (9h 28m) — should NOT refresh
        before_threshold = datetime.datetime(
            2025, 1, 15, 9, 28, 0, tzinfo=datetime.timezone.utc
        )
        with patch(
            "custom_components.beurer_cosynight.beurer_cosynight.datetime"
        ) as mock_dt:
            mock_dt.datetime.now.return_value = before_threshold
            mock_dt.datetime.strptime = datetime.datetime.strptime
            mock_dt.timezone = datetime.timezone
            await hub._refresh_token()

        assert hub._token.access_token == "boundary-token"

    async def test_token_after_refresh_threshold_is_refreshed(self, tmp_path):
        """Token past 80% lifetime should be proactively refreshed."""
        import datetime
        from unittest.mock import patch

        from custom_components.beurer_cosynight.beurer_cosynight import (
            BeurerCosyNight,
            _Token,
        )

        client = FakeHttpClient([TOKEN_RESPONSE])
        hub = BeurerCosyNight(
            client,
            token_path=str(tmp_path / "token"),
            username="u",
            password="p",
        )
        # 12-hour token: issued at 00:00, expires at 12:00
        hub._token = _Token(
            access_token="old-token",
            expires="Wed, 15 Jan 2025 12:00:00 GMT",
            issued="Wed, 15 Jan 2025 00:00:00 GMT",
            expires_in=43200,
            refresh_token="old-refresh",
            token_type="Bearer",
            user_email="test@example.com",
            user_id="user-123",
        )

        # At 81% of lifetime (9h 43m) — should refresh proactively
        after_threshold = datetime.datetime(
            2025, 1, 15, 9, 43, 0, tzinfo=datetime.timezone.utc
        )
        with patch(
            "custom_components.beurer_cosynight.beurer_cosynight.datetime"
        ) as mock_dt:
            mock_dt.datetime.now.return_value = after_threshold
            mock_dt.datetime.strptime = datetime.datetime.strptime
            mock_dt.timezone = datetime.timezone
            await hub._refresh_token()

        # Token was refreshed
        assert hub._token.access_token == "test-access-token"


class TestAsyncGetStatusEdgeCases:
    """Edge cases for get_status — restored from sync tests."""

    async def test_get_status_handles_api_typo(self):
        """API returns 'requieresUpdate', client should map to 'requiresUpdate'."""
        from custom_components.beurer_cosynight.beurer_cosynight import (
            BeurerCosyNight,
            _Token,
        )

        response = dict(STATUS_RESPONSE)
        response["requieresUpdate"] = True

        client = FakeHttpClient([response])
        hub = BeurerCosyNight(client, token_path="/dev/null")
        hub._token = _Token(**VALID_TOKEN)
        status = await hub.get_status("device-123")
        assert status.requiresUpdate is True


class TestAsyncListDevicesEdgeCases:
    """Edge cases for list_devices — restored from sync tests."""

    async def test_list_devices_multiple(self):
        """Multiple devices should all be returned."""
        from custom_components.beurer_cosynight.beurer_cosynight import (
            BeurerCosyNight,
            _Token,
        )

        response = {
            "devices": [
                {
                    "active": True,
                    "id": "dev-1",
                    "name": "Pad 1",
                    "requieresUpdate": False,
                },
                {
                    "active": False,
                    "id": "dev-2",
                    "name": "Pad 2",
                    "requieresUpdate": True,
                },
            ]
        }

        client = FakeHttpClient([response])
        hub = BeurerCosyNight(client, token_path="/dev/null")
        hub._token = _Token(**VALID_TOKEN)
        devices = await hub.list_devices()

        assert len(devices) == 2
        assert devices[1].id == "dev-2"
        assert devices[1].active is False

    async def test_list_devices_missing_key_returns_empty(self):
        """Response without 'devices' key should return empty list."""
        from custom_components.beurer_cosynight.beurer_cosynight import (
            BeurerCosyNight,
            _Token,
        )

        client = FakeHttpClient([{}])
        hub = BeurerCosyNight(client, token_path="/dev/null")
        hub._token = _Token(**VALID_TOKEN)
        devices = await hub.list_devices()
        assert devices == []


class TestAsyncQuickstartEdgeCases:
    """Edge cases for quickstart — restored from sync tests."""

    async def test_quickstart_api_error(self):
        """ApiError from quickstart should propagate."""
        from custom_components.beurer_cosynight.beurer_cosynight import (
            ApiError,
            BeurerCosyNight,
            Quickstart,
            _Token,
        )

        client = FakeHttpClient()
        client.add_error(ApiError("500 Server Error"))
        hub = BeurerCosyNight(client, token_path="/dev/null")
        hub._token = _Token(**VALID_TOKEN)
        qs = Quickstart(bodySetting=3, feetSetting=5, id="d1", timespan=3600)
        with pytest.raises(ApiError):
            await hub.quickstart(qs)
