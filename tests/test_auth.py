from __future__ import annotations

import httpx
import pytest

from workday_api.auth import OAuthRefreshTokenBearerAuth


@pytest.mark.asyncio
async def test_oauth_refresh_token_includes_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {"access_token": "scoped", "expires_in": 3600}

    class FakeAsyncClient:
        def __init__(self, *, timeout: float) -> None:
            pass

        async def __aenter__(self) -> FakeAsyncClient:
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

        async def post(self, url: str, *, data: dict[str, str]) -> FakeResponse:
            captured["data"] = data
            return FakeResponse()

    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)

    auth = OAuthRefreshTokenBearerAuth(
        token_url="https://example.test/token",
        client_id="cid",
        client_secret="sec",
        refresh_token="rt",
        scope="openid",
    )
    headers = await auth.headers()

    assert headers["Authorization"] == "Bearer scoped"
    data = captured["data"]
    assert isinstance(data, dict)
    assert data["scope"] == "openid"


@pytest.mark.asyncio
async def test_oauth_token_request_failure_includes_404_hint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeResponse:
        status_code = 404
        text = "Not Found"

        def raise_for_status(self) -> None:
            raise httpx.HTTPStatusError("404", request=None, response=self)

    class FakeAsyncClient:
        def __init__(self, *, timeout: float) -> None:
            pass

        async def __aenter__(self) -> FakeAsyncClient:
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

        async def post(self, url: str, *, data: dict[str, str]) -> FakeResponse:
            return FakeResponse()

    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)

    auth = OAuthRefreshTokenBearerAuth(
        token_url="https://example.test/bad-token",
        client_id="cid",
        client_secret="sec",
        refresh_token="rt",
    )
    with pytest.raises(ValueError, match="WORKDAY_TOKEN_URL") as exc_info:
        await auth.get_access_token()
    assert "404" in str(exc_info.value)


@pytest.mark.asyncio
async def test_oauth_token_response_missing_access_token(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {"expires_in": 3600}

    class FakeAsyncClient:
        def __init__(self, *, timeout: float) -> None:
            pass

        async def __aenter__(self) -> FakeAsyncClient:
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

        async def post(self, url: str, *, data: dict[str, str]) -> FakeResponse:
            return FakeResponse()

    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)

    auth = OAuthRefreshTokenBearerAuth(
        token_url="https://example.test/token",
        client_id="cid",
        client_secret="sec",
        refresh_token="rt",
    )
    with pytest.raises(ValueError, match="missing access_token"):
        await auth.get_access_token()


@pytest.mark.asyncio
async def test_oauth_token_uses_default_expiry_when_invalid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {"access_token": "t", "expires_in": "not-a-number"}

    class FakeAsyncClient:
        def __init__(self, *, timeout: float) -> None:
            pass

        async def __aenter__(self) -> FakeAsyncClient:
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

        async def post(self, url: str, *, data: dict[str, str]) -> FakeResponse:
            return FakeResponse()

    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)

    auth = OAuthRefreshTokenBearerAuth(
        token_url="https://example.test/token",
        client_id="cid",
        client_secret="sec",
        refresh_token="rt",
    )
    token = await auth.get_access_token()
    assert token == "t"
    assert auth._expires_at_s is not None
