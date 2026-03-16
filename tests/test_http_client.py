"""Tests for HttpClient protocol compliance and FakeHttpClient behavior."""

from __future__ import annotations

import pytest

from tests.conftest import FakeHttpClient


class TestFakeHttpClientProtocol:
    """Verify FakeHttpClient conforms to the HttpClient protocol."""

    def test_conforms_to_http_client_protocol(self, fake_http_client):
        """FakeHttpClient should be recognized as an HttpClient."""
        from custom_components.beurer_cosynight.beurer_cosynight import HttpClient

        assert isinstance(fake_http_client, HttpClient)

    def test_has_get_method(self, fake_http_client):
        """FakeHttpClient must have an async get() method."""

        assert hasattr(fake_http_client, "get")

    def test_has_post_method(self, fake_http_client):
        """FakeHttpClient must have an async post() method."""

        assert hasattr(fake_http_client, "post")

    def test_has_close_method(self, fake_http_client):
        """FakeHttpClient must have an async close() method."""

        assert hasattr(fake_http_client, "close")


class TestFakeHttpClientBehavior:
    """Test FakeHttpClient response queuing and request recording."""

    async def test_get_returns_queued_response(self):
        client = FakeHttpClient([{"key": "value"}])
        result = await client.get("http://example.com")
        assert result == {"key": "value"}

    async def test_post_returns_queued_response(self):
        client = FakeHttpClient([{"key": "value"}])
        result = await client.post("http://example.com", json={"x": 1})
        assert result == {"key": "value"}

    async def test_records_get_requests(self):
        client = FakeHttpClient([{"ok": True}])
        await client.get("http://example.com/api", headers={"Auth": "Bearer tok"})
        assert len(client.requests) == 1
        method, url, kwargs = client.requests[0]
        assert method == "GET"
        assert url == "http://example.com/api"
        assert kwargs["headers"] == {"Auth": "Bearer tok"}

    async def test_records_post_requests_with_data(self):
        client = FakeHttpClient([{"ok": True}])
        await client.post("http://example.com/api", data={"grant_type": "password"})
        method, url, kwargs = client.requests[0]
        assert method == "POST"
        assert kwargs["data"] == {"grant_type": "password"}

    async def test_records_post_requests_with_json(self):
        client = FakeHttpClient([{"ok": True}])
        await client.post("http://example.com/api", json={"id": "device-1"})
        kwargs = client.requests[0][2]
        assert kwargs["json"] == {"id": "device-1"}

    async def test_raises_queued_auth_error(self):
        """FakeHttpClient should raise AuthError when queued."""
        from custom_components.beurer_cosynight.beurer_cosynight import AuthError

        client = FakeHttpClient()
        client.add_error(AuthError("unauthorized"))
        with pytest.raises(AuthError):
            await client.get("http://example.com")

    async def test_raises_queued_api_error(self):
        """FakeHttpClient should raise ApiError when queued."""
        from custom_components.beurer_cosynight.beurer_cosynight import ApiError

        client = FakeHttpClient()
        client.add_error(ApiError("server error"))
        with pytest.raises(ApiError):
            await client.post("http://example.com")

    async def test_no_responses_left_raises_runtime_error(self):
        client = FakeHttpClient()
        with pytest.raises(RuntimeError, match="no more queued responses"):
            await client.get("http://example.com")

    async def test_close_sets_closed_flag(self):
        client = FakeHttpClient()
        assert not client.closed
        await client.close()
        assert client.closed

    async def test_multiple_responses_consumed_in_order(self):
        client = FakeHttpClient([{"first": True}, {"second": True}])
        r1 = await client.get("http://a")
        r2 = await client.post("http://b")
        assert r1 == {"first": True}
        assert r2 == {"second": True}

    async def test_add_response_appends_to_queue(self):
        client = FakeHttpClient()
        client.add_response({"added": True})
        result = await client.get("http://x")
        assert result == {"added": True}

    async def test_mixed_responses_and_errors(self):
        """Interleaved successes and errors should work."""
        from custom_components.beurer_cosynight.beurer_cosynight import ApiError

        client = FakeHttpClient([{"ok": True}])
        client.add_error(ApiError("fail"))
        client.add_response({"recovered": True})

        r1 = await client.get("http://a")
        assert r1 == {"ok": True}

        with pytest.raises(ApiError):
            await client.get("http://b")

        r3 = await client.get("http://c")
        assert r3 == {"recovered": True}
