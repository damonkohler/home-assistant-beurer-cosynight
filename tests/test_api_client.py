"""Tests for the Beurer CosyNight API client."""

from __future__ import annotations

import dataclasses
import datetime
import json
import os
import tempfile
from unittest.mock import patch

import pytest
import requests
import requests_mock as rm

from custom_components.beurer_cosynight.beurer_cosynight import (
    _BASE_URL as BASE_URL,
    BeurerCosyNight,
    Device,
    Quickstart,
    Status,
    _Token,
)

# A token response as the API would return it
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

# An expired token for testing refresh
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

# A valid (non-expired) token for disk persistence
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
    # Note: API returns typo "requieresUpdate"
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


class TestConstructor:
    """Test BeurerCosyNight constructor."""

    def test_constructor_does_not_do_file_io(self, tmp_path):
        """Constructor should NOT do file I/O — deferred to authenticate()."""
        token_path = str(tmp_path / "nonexistent_token")
        # Should not raise or attempt file access
        hub = BeurerCosyNight(
            token_path=token_path, username="user", password="pass"
        )
        assert hub._token is None
        assert hub._token_path == token_path

    def test_default_token_path(self):
        """Default token path should be 'token'."""
        hub = BeurerCosyNight()
        assert hub._token_path == "token"


class TestTokenPersistence:
    """Test token loading and saving lifecycle."""

    def test_load_token_from_disk(self, tmp_path):
        """Token should be loaded from disk during authenticate."""
        token_path = str(tmp_path / "token")
        with open(token_path, "w") as f:
            json.dump(VALID_TOKEN, f)

        hub = BeurerCosyNight(token_path=token_path, username="u", password="p")

        with rm.Mocker() as m:
            # Should not need to authenticate if token is valid
            m.post(BASE_URL + "/token", json=TOKEN_RESPONSE)
            hub.authenticate("u", "p")

        assert hub._token is not None
        assert hub._token.access_token == "valid-access-token"

    def test_save_token_to_disk(self, tmp_path):
        """Token should be saved to disk after authentication."""
        token_path = str(tmp_path / "storage" / "token")

        hub = BeurerCosyNight(token_path=token_path, username="u", password="p")

        with rm.Mocker() as m:
            m.post(BASE_URL + "/token", json=TOKEN_RESPONSE)
            hub.authenticate("u", "p")

        assert os.path.exists(token_path)
        with open(token_path) as f:
            saved = json.load(f)
        assert saved["access_token"] == "test-access-token"

    def test_load_token_corrupt_json(self, tmp_path):
        """Corrupt token file should be handled gracefully."""
        token_path = str(tmp_path / "token")
        with open(token_path, "w") as f:
            f.write("not valid json {{{")

        hub = BeurerCosyNight(token_path=token_path, username="u", password="p")

        with rm.Mocker() as m:
            m.post(BASE_URL + "/token", json=TOKEN_RESPONSE)
            hub.authenticate("u", "p")

        # Should have fallen back to password auth
        assert hub._token.access_token == "test-access-token"

    def test_load_token_missing_fields(self, tmp_path):
        """Token file with missing fields should be handled gracefully."""
        token_path = str(tmp_path / "token")
        with open(token_path, "w") as f:
            json.dump({"access_token": "only"}, f)

        hub = BeurerCosyNight(token_path=token_path, username="u", password="p")

        with rm.Mocker() as m:
            m.post(BASE_URL + "/token", json=TOKEN_RESPONSE)
            hub.authenticate("u", "p")

        # Should fall back to password auth
        assert hub._token.access_token == "test-access-token"

    def test_save_token_permission_error(self, tmp_path):
        """Failed token persistence should not raise."""
        # Use a path that can't be written to
        token_path = "/nonexistent_root_dir/token"

        hub = BeurerCosyNight(token_path=token_path, username="u", password="p")

        with rm.Mocker() as m:
            m.post(BASE_URL + "/token", json=TOKEN_RESPONSE)
            # Should not raise even though token can't be saved
            hub.authenticate("u", "p")

        assert hub._token.access_token == "test-access-token"


class TestAuthentication:
    """Test authentication flows."""

    def test_authenticate_with_password(self, tmp_path):
        """Successful password authentication."""
        hub = BeurerCosyNight(
            token_path=str(tmp_path / "token"),
            username="user@test.com",
            password="pass",
        )

        with rm.Mocker() as m:
            m.post(BASE_URL + "/token", json=TOKEN_RESPONSE)
            hub.authenticate("user@test.com", "pass")

        assert hub._token is not None
        assert hub._token.access_token == "test-access-token"
        assert hub._token.token_type == "Bearer"

    def test_authenticate_stores_credentials(self, tmp_path):
        """authenticate() should store credentials for future re-auth."""
        hub = BeurerCosyNight(token_path=str(tmp_path / "token"))

        with rm.Mocker() as m:
            m.post(BASE_URL + "/token", json=TOKEN_RESPONSE)
            hub.authenticate("user@test.com", "mypass")

        assert hub._username == "user@test.com"
        assert hub._password == "mypass"

    def test_authenticate_http_error(self, tmp_path):
        """HTTP error during authentication should propagate."""
        hub = BeurerCosyNight(
            token_path=str(tmp_path / "token"), username="u", password="p"
        )

        with rm.Mocker() as m:
            m.post(BASE_URL + "/token", status_code=401)
            with pytest.raises(requests.HTTPError):
                hub.authenticate("u", "p")

    def test_authenticate_network_error(self, tmp_path):
        """Network error during authentication should propagate."""
        hub = BeurerCosyNight(
            token_path=str(tmp_path / "token"), username="u", password="p"
        )

        with rm.Mocker() as m:
            m.post(BASE_URL + "/token", exc=requests.ConnectionError("no network"))
            with pytest.raises(requests.ConnectionError):
                hub.authenticate("u", "p")

    def test_authenticate_sends_correct_payload(self, tmp_path):
        """Password auth should send correct grant_type and credentials."""
        hub = BeurerCosyNight(
            token_path=str(tmp_path / "token"), username="u", password="p"
        )

        with rm.Mocker() as m:
            m.post(BASE_URL + "/token", json=TOKEN_RESPONSE)
            hub.authenticate("user@test.com", "pass123")

        assert m.last_request.body == (
            "grant_type=password&username=user%40test.com&password=pass123"
        )


class TestTokenRefresh:
    """Test token refresh logic."""

    def test_refresh_expired_token(self, tmp_path):
        """Expired token should be refreshed."""
        token_path = str(tmp_path / "token")
        with open(token_path, "w") as f:
            json.dump(EXPIRED_TOKEN, f)

        hub = BeurerCosyNight(token_path=token_path, username="u", password="p")

        with rm.Mocker() as m:
            # First call: authenticate loads expired token, calls _refresh_token
            # which sees it's expired and posts refresh request
            m.post(BASE_URL + "/token", json=TOKEN_RESPONSE)
            hub.authenticate("u", "p")

        assert hub._token.access_token == "test-access-token"

    def test_refresh_failure_falls_back_to_reauth(self, tmp_path):
        """Failed refresh with stored credentials should re-authenticate."""
        token_path = str(tmp_path / "token")
        with open(token_path, "w") as f:
            json.dump(EXPIRED_TOKEN, f)

        hub = BeurerCosyNight(token_path=token_path, username="u", password="p")

        with rm.Mocker() as m:
            # First POST (refresh) fails, second POST (password auth) succeeds
            m.post(
                BASE_URL + "/token",
                [
                    {"status_code": 401},
                    {"json": TOKEN_RESPONSE},
                ],
            )
            hub.authenticate("u", "p")

        assert hub._token.access_token == "test-access-token"

    def test_refresh_failure_no_credentials_raises(self):
        """Failed refresh without stored credentials should raise."""
        hub = BeurerCosyNight()
        # Manually set an expired token without credentials
        hub._token = _Token(**EXPIRED_TOKEN)

        with rm.Mocker() as m:
            m.post(BASE_URL + "/token", status_code=401)
            with pytest.raises(BeurerCosyNight.Error):
                hub._refresh_token()

    def test_no_token_no_credentials_raises(self):
        """No token and no credentials should raise."""
        hub = BeurerCosyNight()
        with pytest.raises(BeurerCosyNight.Error, match="Not authenticated"):
            hub._refresh_token()

    def test_no_token_with_credentials_authenticates(self, tmp_path):
        """No token but with credentials should do full auth."""
        hub = BeurerCosyNight(
            token_path=str(tmp_path / "token"), username="u", password="p"
        )

        with rm.Mocker() as m:
            m.post(BASE_URL + "/token", json=TOKEN_RESPONSE)
            hub._refresh_token()

        assert hub._token.access_token == "test-access-token"

    def test_token_at_exact_expiry_boundary_not_refreshed(self, tmp_path):
        """Token at exact expiry time should NOT be refreshed (> not >=)."""
        expiry_str = "Wed, 15 Jan 2025 12:00:00 GMT"
        hub = BeurerCosyNight(
            token_path=str(tmp_path / "token"), username="u", password="p"
        )
        hub._token = _Token(
            access_token="boundary-token",
            expires=expiry_str,
            issued="Wed, 15 Jan 2025 00:00:00 GMT",
            expires_in=43200,
            refresh_token="boundary-refresh",
            token_type="Bearer",
            user_email="test@example.com",
            user_id="user-123",
        )

        exact_expiry = datetime.datetime(2025, 1, 15, 12, 0, 0, tzinfo=datetime.timezone.utc)
        with patch(
            "custom_components.beurer_cosynight.beurer_cosynight.datetime"
        ) as mock_dt:
            mock_dt.datetime.now.return_value = exact_expiry
            mock_dt.datetime.strptime = datetime.datetime.strptime
            mock_dt.timezone = datetime.timezone
            hub._refresh_token()

        assert hub._token.access_token == "boundary-token"

    def test_token_cleared_when_refresh_and_reauth_both_fail(self):
        """After refresh + re-auth failure, token must be None."""
        hub = BeurerCosyNight(username="u", password="p")
        hub._token = _Token(**EXPIRED_TOKEN)

        with rm.Mocker() as m:
            m.post(BASE_URL + "/token", status_code=401)
            with pytest.raises(Exception):
                hub._refresh_token()

        assert hub._token is None

    def test_token_cleared_when_refresh_fails_no_credentials(self):
        """After refresh failure without credentials, token must be None."""
        hub = BeurerCosyNight()
        hub._token = _Token(**EXPIRED_TOKEN)

        with rm.Mocker() as m:
            m.post(BASE_URL + "/token", status_code=401)
            with pytest.raises(BeurerCosyNight.Error):
                hub._refresh_token()

        assert hub._token is None

    def test_valid_token_not_refreshed(self, tmp_path):
        """Valid (non-expired) token should not be refreshed."""
        token_path = str(tmp_path / "token")
        with open(token_path, "w") as f:
            json.dump(VALID_TOKEN, f)

        hub = BeurerCosyNight(token_path=token_path, username="u", password="p")

        with rm.Mocker() as m:
            # No POST needed since token is valid
            hub.authenticate("u", "p")

        # Token should still be the loaded valid one
        assert hub._token.access_token == "valid-access-token"


class TestGetStatus:
    """Test get_status API method."""

    def test_get_status_success(self):
        """Successful get_status should return Status dataclass."""
        hub = BeurerCosyNight(username="u", password="p")
        hub._token = _Token(**VALID_TOKEN)

        with rm.Mocker() as m:
            m.post(BASE_URL + "/api/v1/Device/GetStatus", json=STATUS_RESPONSE)
            status = hub.get_status("device-123")

        assert isinstance(status, Status)
        assert status.bodySetting == 3
        assert status.feetSetting == 5
        assert status.timer == 1800
        assert status.requiresUpdate is False
        assert status.id == "device-123"

    def test_get_status_sends_device_id(self):
        """get_status should send device ID in request body."""
        hub = BeurerCosyNight(username="u", password="p")
        hub._token = _Token(**VALID_TOKEN)

        with rm.Mocker() as m:
            m.post(BASE_URL + "/api/v1/Device/GetStatus", json=STATUS_RESPONSE)
            hub.get_status("device-123")

        assert m.last_request.json() == {"id": "device-123"}

    def test_get_status_uses_auth_header(self):
        """get_status should include Bearer token in Authorization header."""
        hub = BeurerCosyNight(username="u", password="p")
        hub._token = _Token(**VALID_TOKEN)

        with rm.Mocker() as m:
            m.post(BASE_URL + "/api/v1/Device/GetStatus", json=STATUS_RESPONSE)
            hub.get_status("device-123")

        assert m.last_request.headers["Authorization"] == "Bearer valid-access-token"

    def test_get_status_http_error(self):
        """HTTP error from get_status should propagate."""
        hub = BeurerCosyNight(username="u", password="p")
        hub._token = _Token(**VALID_TOKEN)

        with rm.Mocker() as m:
            m.post(BASE_URL + "/api/v1/Device/GetStatus", status_code=500)
            with pytest.raises(requests.HTTPError):
                hub.get_status("device-123")

    def test_get_status_handles_api_typo(self):
        """API returns 'requieresUpdate', client should map to 'requiresUpdate'."""
        hub = BeurerCosyNight(username="u", password="p")
        hub._token = _Token(**VALID_TOKEN)

        response = dict(STATUS_RESPONSE)
        response["requieresUpdate"] = True

        with rm.Mocker() as m:
            m.post(BASE_URL + "/api/v1/Device/GetStatus", json=response)
            status = hub.get_status("device-123")

        assert status.requiresUpdate is True


class TestListDevices:
    """Test list_devices API method."""

    def test_list_devices_success(self):
        """Successful list_devices should return list of Device objects."""
        hub = BeurerCosyNight(username="u", password="p")
        hub._token = _Token(**VALID_TOKEN)

        with rm.Mocker() as m:
            m.get(BASE_URL + "/api/v1/Device/List", json=LIST_DEVICES_RESPONSE)
            devices = hub.list_devices()

        assert len(devices) == 1
        assert isinstance(devices[0], Device)
        assert devices[0].id == "device-123"
        assert devices[0].name == "My Pad"
        assert devices[0].active is True

    def test_list_devices_empty(self):
        """Empty device list should return empty list."""
        hub = BeurerCosyNight(username="u", password="p")
        hub._token = _Token(**VALID_TOKEN)

        with rm.Mocker() as m:
            m.get(BASE_URL + "/api/v1/Device/List", json={"devices": []})
            devices = hub.list_devices()

        assert devices == []

    def test_list_devices_multiple(self):
        """Multiple devices should all be returned."""
        hub = BeurerCosyNight(username="u", password="p")
        hub._token = _Token(**VALID_TOKEN)

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

        with rm.Mocker() as m:
            m.get(BASE_URL + "/api/v1/Device/List", json=response)
            devices = hub.list_devices()

        assert len(devices) == 2
        assert devices[1].id == "dev-2"
        assert devices[1].active is False


class TestQuickstart:
    """Test quickstart API method."""

    def test_quickstart_success(self):
        """Successful quickstart should not raise."""
        hub = BeurerCosyNight(username="u", password="p")
        hub._token = _Token(**VALID_TOKEN)

        qs = Quickstart(bodySetting=3, feetSetting=5, id="device-123", timespan=3600)

        with rm.Mocker() as m:
            m.post(BASE_URL + "/api/v1/Device/Quickstart", status_code=200)
            hub.quickstart(qs)

    def test_quickstart_sends_correct_payload(self):
        """quickstart should send all Quickstart fields."""
        hub = BeurerCosyNight(username="u", password="p")
        hub._token = _Token(**VALID_TOKEN)

        qs = Quickstart(bodySetting=3, feetSetting=5, id="device-123", timespan=3600)

        with rm.Mocker() as m:
            m.post(BASE_URL + "/api/v1/Device/Quickstart", status_code=200)
            hub.quickstart(qs)

        assert m.last_request.json() == {
            "bodySetting": 3,
            "feetSetting": 5,
            "id": "device-123",
            "timespan": 3600,
        }

    def test_quickstart_stop(self):
        """Quickstart with 0/0/0 should stop the device."""
        hub = BeurerCosyNight(username="u", password="p")
        hub._token = _Token(**VALID_TOKEN)

        qs = Quickstart(bodySetting=0, feetSetting=0, id="device-123", timespan=0)

        with rm.Mocker() as m:
            m.post(BASE_URL + "/api/v1/Device/Quickstart", status_code=200)
            hub.quickstart(qs)

        assert m.last_request.json()["bodySetting"] == 0
        assert m.last_request.json()["feetSetting"] == 0
        assert m.last_request.json()["timespan"] == 0

    def test_quickstart_http_error(self):
        """HTTP error from quickstart should propagate."""
        hub = BeurerCosyNight(username="u", password="p")
        hub._token = _Token(**VALID_TOKEN)

        qs = Quickstart(bodySetting=3, feetSetting=5, id="device-123", timespan=3600)

        with rm.Mocker() as m:
            m.post(BASE_URL + "/api/v1/Device/Quickstart", status_code=500)
            with pytest.raises(requests.HTTPError):
                hub.quickstart(qs)


class TestDataclasses:
    """Test data classes."""

    def test_device_fields(self):
        """Device dataclass should hold all fields."""
        d = Device(active=True, id="d1", name="Pad", requiresUpdate=False)
        assert d.active is True
        assert d.id == "d1"
        assert d.name == "Pad"
        assert d.requiresUpdate is False

    def test_status_fields(self):
        """Status dataclass should hold all fields."""
        s = Status(
            active=True,
            bodySetting=3,
            feetSetting=5,
            heartbeat=100,
            id="d1",
            name="Pad",
            requiresUpdate=False,
            timer=1800,
        )
        assert s.timer == 1800
        assert s.bodySetting == 3

    def test_quickstart_fields(self):
        """Quickstart dataclass should hold all fields."""
        q = Quickstart(bodySetting=3, feetSetting=5, id="d1", timespan=3600)
        assert dataclasses.asdict(q) == {
            "bodySetting": 3,
            "feetSetting": 5,
            "id": "d1",
            "timespan": 3600,
        }
