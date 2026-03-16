"""Beurer CosyNight API client."""

import dataclasses
import datetime
import json
import logging
import os

import requests

_BASE_URL = "https://cosynight.azurewebsites.net"
_DATETIME_FORMAT = "%a, %d %b %Y %H:%M:%S %Z"
_REQUEST_TIMEOUT = 10
_LOGGER = logging.getLogger(__name__)


@dataclasses.dataclass
class Device:
    active: bool
    id: str
    name: str
    requiresUpdate: bool


@dataclasses.dataclass
class Quickstart:
    bodySetting: int
    feetSetting: int
    id: str
    timespan: int  # Seconds


@dataclasses.dataclass
class Status:
    active: bool
    bodySetting: int
    feetSetting: int
    heartbeat: int
    id: str
    name: str
    requiresUpdate: bool
    timer: int


@dataclasses.dataclass
class _Token:
    access_token: str
    expires: str
    expires_in: int
    issued: str
    refresh_token: str
    token_type: str
    user_email: str
    user_id: str


class _TokenAuth(requests.auth.AuthBase):

    def __init__(self, token: _Token) -> None:
        self._token = token

    def __call__(self, request):
        request.headers["Authorization"] = (
            f"{self._token.token_type} {self._token.access_token}"
        )
        return request


class BeurerCosyNight:

    class Error(Exception):
        pass

    def __init__(
        self,
        token_path: str | None = None,
        username: str | None = None,
        password: str | None = None,
    ) -> None:
        self._token: _Token | None = None
        self._token_path = token_path or "token"
        self._username = username
        self._password = password

    def _load_token(self) -> None:
        """Load token from disk if it exists."""
        try:
            if os.path.exists(self._token_path):
                with open(self._token_path) as f:
                    self._token = _Token(**json.load(f))
                _LOGGER.debug("Loaded token from %s", self._token_path)
        except (json.JSONDecodeError, TypeError, OSError) as err:
            _LOGGER.warning("Failed to load token from %s: %s", self._token_path, err)
            self._token = None

    def _update_token(self, response: requests.Response) -> None:
        """Parse token response and persist to disk."""
        body = response.json()
        body["expires"] = body.pop(".expires")
        body["issued"] = body.pop(".issued")
        self._token = _Token(**body)
        try:
            os.makedirs(os.path.dirname(self._token_path) or ".", exist_ok=True)
            with open(self._token_path, "w") as f:
                json.dump(dataclasses.asdict(self._token), f)
            _LOGGER.debug("Token persisted to %s", self._token_path)
        except OSError as err:
            _LOGGER.warning("Failed to persist token to %s: %s", self._token_path, err)

    def _refresh_token(self) -> None:
        """Refresh the access token, falling back to re-authentication on failure."""
        if self._token is None:
            if self._username and self._password:
                _LOGGER.debug("No token, performing full authentication")
                self._authenticate_with_password(self._username, self._password)
                return
            raise self.Error("Not authenticated and no credentials stored")

        expires = datetime.datetime.strptime(self._token.expires, _DATETIME_FORMAT)
        expires = expires.replace(tzinfo=datetime.timezone.utc)
        if datetime.datetime.now(datetime.timezone.utc) > expires:
            _LOGGER.debug("Token expired, refreshing")
            try:
                r = requests.post(
                    _BASE_URL + "/token",
                    data={
                        "grant_type": "refresh_token",
                        "refresh_token": self._token.refresh_token,
                    },
                    timeout=_REQUEST_TIMEOUT,
                )
                r.raise_for_status()
                self._update_token(r)
            except requests.RequestException as err:
                _LOGGER.warning("Token refresh failed: %s", err)
                self._token = None
                if self._username and self._password:
                    _LOGGER.info("Attempting re-authentication with stored credentials")
                    self._authenticate_with_password(self._username, self._password)
                else:
                    raise self.Error(
                        "Token refresh failed and no credentials stored"
                    ) from err

    def _authenticate_with_password(self, username: str, password: str) -> None:
        """Authenticate with username/password credentials."""
        _LOGGER.debug("Requesting new token for %s", username)
        r = requests.post(
            _BASE_URL + "/token",
            data={
                "grant_type": "password",
                "username": username,
                "password": password,
            },
            timeout=_REQUEST_TIMEOUT,
        )
        r.raise_for_status()
        self._update_token(r)

    def authenticate(self, username: str, password: str) -> None:
        """Authenticate and store credentials for future re-authentication."""
        self._username = username
        self._password = password
        self._load_token()
        if self._token is None:
            self._authenticate_with_password(username, password)
        else:
            self._refresh_token()

    def get_status(self, device_id: str) -> Status:
        self._refresh_token()
        r = requests.post(
            _BASE_URL + "/api/v1/Device/GetStatus",
            json={"id": device_id},
            auth=_TokenAuth(self._token),
            timeout=_REQUEST_TIMEOUT,
        )
        r.raise_for_status()
        body = r.json()
        body["requiresUpdate"] = body.pop("requieresUpdate")
        return Status(**body)

    def list_devices(self) -> list[Device]:
        self._refresh_token()
        r = requests.get(
            _BASE_URL + "/api/v1/Device/List",
            auth=_TokenAuth(self._token),
            timeout=_REQUEST_TIMEOUT,
        )
        r.raise_for_status()
        devices = []
        for d in r.json().get("devices", []):
            d["requiresUpdate"] = d.pop("requieresUpdate")
            devices.append(Device(**d))
        return devices

    def quickstart(self, quickstart: Quickstart) -> None:
        self._refresh_token()
        r = requests.post(
            _BASE_URL + "/api/v1/Device/Quickstart",
            json=dataclasses.asdict(quickstart),
            auth=_TokenAuth(self._token),
            timeout=_REQUEST_TIMEOUT,
        )
        r.raise_for_status()
