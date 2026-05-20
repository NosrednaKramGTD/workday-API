from __future__ import annotations

import httpx
import pytest

import workday_api.rest as rest_mod
from workday_api.auth import OAuthRefreshTokenBearerAuth


@pytest.mark.asyncio
async def test_oauth_refresh_token_auth_caches_token(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: dict[str, int] = {"post": 0}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {"access_token": "t1", "expires_in": 3600}

    class FakeAsyncClient:
        def __init__(self, *, timeout: float) -> None:
            self.timeout = timeout

        async def __aenter__(self) -> FakeAsyncClient:
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

        async def post(self, url: str, *, data: dict[str, str]) -> FakeResponse:
            calls["post"] += 1
            assert data["grant_type"] == "refresh_token"
            return FakeResponse()

    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)

    auth = OAuthRefreshTokenBearerAuth(
        token_url="https://example.test/token",
        client_id="cid",
        client_secret="sec",
        refresh_token="rt",
    )

    h1 = await auth.headers()
    h2 = await auth.headers()

    assert h1["Authorization"] == "Bearer t1"
    assert h2["Authorization"] == "Bearer t1"
    assert calls["post"] == 1


@pytest.mark.asyncio
async def test_rest_client_sets_correlation_id_and_basic_auth(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {"ok": True}

    class FakeAsyncClient:
        def __init__(self, *, base_url: str, timeout: float) -> None:
            captured["base_url"] = base_url
            captured["timeout"] = timeout

        async def __aenter__(self) -> FakeAsyncClient:
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

        async def request(self, *, method: str, url: str, params, json, data, headers, auth):
            captured["method"] = method
            captured["url"] = url
            captured["params"] = params
            captured["headers"] = headers
            captured["auth"] = auth
            return FakeResponse()

    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)

    client = rest_mod.WorkdayRestClient(
        base_url="https://example.test/",
        auth=rest_mod.BasicRestAuth(username="u", password="p"),
        default_headers={"A": "b"},
        timeout_s=9.0,
    )

    resp = await client.get_json("/v1/test", correlation_id="corr-2", params={"x": "1"})
    assert resp == {"ok": True}

    headers = captured["headers"]
    assert isinstance(headers, dict)
    assert headers["A"] == "b"
    assert headers["X-Correlation-Id"] == "corr-2"
    assert captured["auth"] == ("u", "p")


@pytest.mark.asyncio
async def test_rest_client_oauth_bearer_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class FakeOAuth:
        async def headers(self) -> dict[str, str]:
            return {"Authorization": "Bearer oauth-token"}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {"ok": True}

    class FakeAsyncClient:
        def __init__(self, *, base_url: str, timeout: float) -> None:
            pass

        async def __aenter__(self) -> FakeAsyncClient:
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

        async def request(self, *, method: str, url: str, params, json, data, headers, auth):
            captured["headers"] = headers
            captured["auth"] = auth
            return FakeResponse()

    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)

    client = rest_mod.WorkdayRestClient(
        base_url="https://example.test/",
        auth=FakeOAuth(),
    )
    await client.get_json("/v1/test")
    headers = captured["headers"]
    assert isinstance(headers, dict)
    assert headers["Authorization"] == "Bearer oauth-token"
    assert captured["auth"] is None


@pytest.mark.asyncio
async def test_rest_client_http_error_includes_hints(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeResponse:
        status_code = 404
        headers = httpx.Headers(
            {
                "content-type": "application/json",
                "x-correlation-id": "upstream-corr",
                "set-cookie": "secret=1",
            }
        )
        text = '{"error":"not found: customObjectDefinition"}'

        @property
        def request(self) -> object:
            class Req:
                url = "https://example.test/ccx/service/customreport2/foo"

            return Req()

        def json(self) -> dict[str, str]:
            return {"error": "not found: customObjectDefinition"}

        def raise_for_status(self) -> None:
            raise httpx.HTTPStatusError("404", request=self.request, response=self)

    class FakeAsyncClient:
        def __init__(self, *, base_url: str, timeout: float) -> None:
            pass

        async def __aenter__(self) -> FakeAsyncClient:
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

        async def request(self, *, method: str, url: str, params, json, data, headers, auth):
            return FakeResponse()

    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)

    client = rest_mod.WorkdayRestClient(
        base_url="https://example.test/ccx/service/customreport2/tenant/",
        auth=rest_mod.BasicRestAuth(username="u", password="p"),
    )
    with pytest.raises(rest_mod.WorkdayRestHttpError) as exc_info:
        await client.get_json("/v1/customObjectDefinition", correlation_id="corr-404")

    err = exc_info.value
    assert err.status_code == 404
    assert err.correlation_id == "corr-404"
    assert err.sent_bearer_auth is False
    assert "customObjectDefinition" in str(err)
    assert "RaaS/customreport2" in str(err)
    assert "set-cookie" not in str(err).lower()


@pytest.mark.asyncio
async def test_basic_rest_auth_headers_returns_empty() -> None:
    auth = rest_mod.BasicRestAuth(username="u", password="p")
    assert await auth.headers() == {}


@pytest.mark.asyncio
async def test_rest_client_version_segment_hint(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeResponse:
        status_code = 500
        headers = httpx.Headers({"content-type": "text/plain"})
        text = "error"

        @property
        def request(self) -> object:
            class Req:
                url = "https://example.test/ccx/api/v1/tenant/foo"

            return Req()

        def raise_for_status(self) -> None:
            raise httpx.HTTPStatusError("500", request=self.request, response=self)

    class FakeAsyncClient:
        def __init__(self, *, base_url: str, timeout: float) -> None:
            pass

        async def __aenter__(self) -> FakeAsyncClient:
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

        async def request(self, *, method: str, url: str, params, json, data, headers, auth):
            return FakeResponse()

    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)

    client = rest_mod.WorkdayRestClient(
        base_url="https://example.test/ccx/api/v1/tenant/",
    )
    with pytest.raises(rest_mod.WorkdayRestHttpError, match="/vXX.X"):
        await client.request("GET", "/foo")

