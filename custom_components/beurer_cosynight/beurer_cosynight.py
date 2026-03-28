"""Beurer CosyNight API client."""

from __future__ import annotations

import asyncio
import dataclasses
import datetime
import json
import logging
import os
from typing import Any, Protocol, runtime_checkable

_BASE_URL = "https://cosynight.azurewebsites.net"
_DATETIME_FORMAT = "%a, %d %b %Y %H:%M:%S %Z"
_REQUEST_TIMEOUT = 10
_REFRESH_THRESHOLD = 0.8  # Refresh when 80% of token lifetime has elapsed
_PASSWORD_AUTH_RETRIES = 2
_PASSWORD_AUTH_BACKOFF = 2.0  # Seconds, doubles each retry
_LOGGER = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Error hierarchy
# ---------------------------------------------------------------------------


class BeurerCosyNightError(Exception):
    """Base exception for Beurer CosyNight."""


class AuthError(BeurerCosyNightError):
    """Authentication failed (401/403)."""


class ApiError(BeurerCosyNightError):
    """API communication error."""


# ---------------------------------------------------------------------------
# HTTP client protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class HttpClient(Protocol):
    """Abstract HTTP client for loose coupling and testability."""

    async def get(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> dict[str, Any]: ...

    async def post(
        self,
        url: str,
        *,
        data: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> dict[str, Any]: ...

    async def close(self) -> None: ...


# ---------------------------------------------------------------------------
# AiohttpClient — production implementation
# ---------------------------------------------------------------------------


class AiohttpClient:
    """HttpClient implementation backed by aiohttp.ClientSession."""

    def __init__(self, session) -> None:
        self._session = session

    async def get(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        try:
            async with self._session.get(url, headers=headers, timeout=timeout) as resp:
                if resp.status in (401, 403):
                    raise AuthError(f"HTTP {resp.status}")
                if resp.status >= 400:
                    raise ApiError(f"HTTP {resp.status}")
                return await resp.json()
        except (AuthError, ApiError):
            raise
        except Exception as err:
            raise ApiError(str(err)) from err

    async def post(
        self,
        url: str,
        *,
        data: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        try:
            async with self._session.post(
                url, data=data, json=json, headers=headers, timeout=timeout
            ) as resp:
                if resp.status in (401, 403):
                    raise AuthError(f"HTTP {resp.status}")
                if resp.status >= 400:
                    raise ApiError(f"HTTP {resp.status}")
                return await resp.json()
        except (AuthError, ApiError):
            raise
        except Exception as err:
            raise ApiError(str(err)) from err

    async def close(self) -> None:
        """No-op — HA's shared session is managed by async_get_clientsession."""


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# API client
# ---------------------------------------------------------------------------


class BeurerCosyNight:
    def __init__(
        self,
        client: HttpClient,
        *,
        token_path: str | None = None,
        username: str | None = None,
        password: str | None = None,
    ) -> None:
        self._client = client
        self._token: _Token | None = None
        self._token_path = token_path or "token"
        self._username = username
        self._password = password
        self._refresh_lock = asyncio.Lock()

    def _load_token(self) -> None:
        """Load token from disk if it exists (sync — called via to_thread)."""
        if self._token_path == os.devnull:
            return
        try:
            if os.path.exists(self._token_path):
                with open(self._token_path) as f:
                    self._token = _Token(**json.load(f))
                _LOGGER.debug("Loaded token from %s", self._token_path)
        except (json.JSONDecodeError, TypeError, OSError) as err:
            _LOGGER.warning("Failed to load token from %s: %s", self._token_path, err)
            self._token = None

    def _save_token(self) -> None:
        """Persist token to disk (sync — called via to_thread)."""
        try:
            os.makedirs(os.path.dirname(self._token_path) or ".", exist_ok=True)
            with open(self._token_path, "w") as f:
                json.dump(dataclasses.asdict(self._token), f)
            _LOGGER.debug("Token persisted to %s", self._token_path)
        except OSError as err:
            _LOGGER.warning("Failed to persist token to %s: %s", self._token_path, err)

    async def _update_token(self, body: dict) -> None:
        """Parse token response and persist to disk."""
        body = dict(body)  # don't mutate the original
        body["expires"] = body.pop(".expires")
        body["issued"] = body.pop(".issued")
        self._token = _Token(**body)
        await asyncio.to_thread(self._save_token)

    def _is_expired(self) -> bool:
        """Check if the current token is expired."""
        if self._token is None:
            return True
        expires = datetime.datetime.strptime(self._token.expires, _DATETIME_FORMAT)
        expires = expires.replace(tzinfo=datetime.timezone.utc)
        return datetime.datetime.now(datetime.timezone.utc) > expires

    def _needs_refresh(self) -> bool:
        """Check if the token should be proactively refreshed.

        Returns True if the token is expired OR if more than 80% of the
        token's lifetime has elapsed. Refreshing before expiry avoids
        hitting the API with an already-expired token, which some OAuth
        servers reject.
        """
        if self._token is None:
            return True
        issued = datetime.datetime.strptime(self._token.issued, _DATETIME_FORMAT)
        issued = issued.replace(tzinfo=datetime.timezone.utc)
        expires = datetime.datetime.strptime(self._token.expires, _DATETIME_FORMAT)
        expires = expires.replace(tzinfo=datetime.timezone.utc)
        lifetime = (expires - issued).total_seconds()
        if lifetime <= 0:
            return True
        now = datetime.datetime.now(datetime.timezone.utc)
        elapsed = (now - issued).total_seconds()
        return elapsed >= lifetime * _REFRESH_THRESHOLD

    async def _refresh_token(self) -> None:
        """Refresh the access token with asyncio.Lock to prevent concurrent refresh."""
        async with self._refresh_lock:
            # Re-check inside lock — another coroutine may have refreshed already
            if self._token is not None and not self._needs_refresh():
                return

            if self._token is None:
                if self._username and self._password:
                    _LOGGER.debug("No token, performing full authentication")
                    await self._authenticate_with_password_with_retry(
                        self._username, self._password
                    )
                    return
                raise AuthError("Not authenticated and no credentials stored")

            _LOGGER.debug(
                "Token needs refresh (proactive at %d%% lifetime)",
                int(_REFRESH_THRESHOLD * 100),
            )
            try:
                body = await self._client.post(
                    _BASE_URL + "/token",
                    data={
                        "grant_type": "refresh_token",
                        "refresh_token": self._token.refresh_token,
                    },
                    timeout=_REQUEST_TIMEOUT,
                )
                await self._update_token(body)
            except (AuthError, ApiError) as err:
                _LOGGER.warning("Token refresh failed: %s", err)
                self._token = None
                if self._username and self._password:
                    _LOGGER.info("Attempting re-authentication with stored credentials")
                    await self._authenticate_with_password_with_retry(
                        self._username, self._password
                    )
                else:
                    raise AuthError(
                        "Token refresh failed and no credentials stored"
                    ) from err

    async def _authenticate_with_password(self, username: str, password: str) -> None:
        """Authenticate with username/password credentials."""
        _LOGGER.debug("Requesting new token for %s", username)
        body = await self._client.post(
            _BASE_URL + "/token",
            data={
                "grant_type": "password",
                "username": username,
                "password": password,
            },
            timeout=_REQUEST_TIMEOUT,
        )
        await self._update_token(body)

    async def _authenticate_with_password_with_retry(
        self, username: str, password: str
    ) -> None:
        """Authenticate with username/password, retrying with exponential backoff."""
        last_error: Exception | None = None
        backoff = _PASSWORD_AUTH_BACKOFF
        for attempt in range(_PASSWORD_AUTH_RETRIES + 1):
            try:
                await self._authenticate_with_password(username, password)
                return
            except (AuthError, ApiError) as err:
                last_error = err
                if attempt < _PASSWORD_AUTH_RETRIES:
                    _LOGGER.info(
                        "Password auth attempt %d failed (%s), retrying in %.1fs",
                        attempt + 1,
                        err,
                        backoff,
                    )
                    await asyncio.sleep(backoff)
                    backoff *= 2
        raise last_error  # type: ignore[misc]

    async def authenticate(self, username: str, password: str) -> None:
        """Authenticate and store credentials for future re-authentication."""
        self._username = username
        self._password = password
        await asyncio.to_thread(self._load_token)
        if self._token is None:
            await self._authenticate_with_password(username, password)
        else:
            await self._refresh_token()

    @staticmethod
    def _fix_update_key(body: dict[str, Any]) -> dict[str, Any]:
        """Fix the API typo: rename 'requieresUpdate' to 'requiresUpdate'."""
        body = dict(body)
        body["requiresUpdate"] = body.pop("requieresUpdate")
        return body

    def _auth_headers(self) -> dict[str, str]:
        """Build Authorization header from current token."""
        if self._token is None:
            raise AuthError("Not authenticated")
        return {"Authorization": f"{self._token.token_type} {self._token.access_token}"}

    async def _call_with_auth_retry(
        self, method: str, url: str, **kwargs: Any
    ) -> dict[str, Any]:
        """Call an API endpoint, retrying once on 401 (TOCTOU race protection).

        If the token expired between _refresh_token() and the actual API call,
        force a full refresh and retry the request once.
        """
        await self._refresh_token()
        call = getattr(self._client, method)
        try:
            return await call(url, headers=self._auth_headers(), **kwargs)
        except AuthError:
            _LOGGER.debug(
                "API returned 401 after refresh — forcing re-auth and retrying"
            )
            self._token = None
            await self._refresh_token()
            return await call(url, headers=self._auth_headers(), **kwargs)

    async def get_status(self, device_id: str) -> Status:
        body = await self._call_with_auth_retry(
            "post",
            _BASE_URL + "/api/v1/Device/GetStatus",
            json={"id": device_id},
            timeout=_REQUEST_TIMEOUT,
        )
        return Status(**self._fix_update_key(body))

    async def list_devices(self) -> list[Device]:
        body = await self._call_with_auth_retry(
            "get",
            _BASE_URL + "/api/v1/Device/List",
            timeout=_REQUEST_TIMEOUT,
        )
        return [Device(**self._fix_update_key(d)) for d in body.get("devices", [])]

    async def quickstart(self, quickstart: Quickstart) -> Status:
        body = await self._call_with_auth_retry(
            "post",
            _BASE_URL + "/api/v1/Device/Quickstart",
            json=dataclasses.asdict(quickstart),
            timeout=_REQUEST_TIMEOUT,
        )
        return Status(**self._fix_update_key(body))
