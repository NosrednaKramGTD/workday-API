from __future__ import annotations

import httpx
import pytest

from workday_api.auth import OAuthRefreshTokenBearerAuth
from workday_api.soap import WorkdaySoapClient, WorkdaySoapError, wsse_username_token_header


def test_wsse_username_token_header_escapes_special_characters() -> None:
    header = wsse_username_token_header(username="user&<", password='pass"\'')
    assert "<wsse:Username>user&amp;&lt;</wsse:Username>" in header
    assert "<wsse:Password>pass&quot;&apos;</wsse:Password>" in header


@pytest.mark.asyncio
async def test_soap_call_with_wsse_username_token(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class FakeResponse:
        status_code = 200
        text = "<response/>"
        headers: dict[str, str] = {}

        @property
        def request(self) -> object:
            class Req:
                method = "POST"
                url = "https://example.test/soap"

            return Req()

        def raise_for_status(self) -> None:
            return None

    class FakeAsyncClient:
        def __init__(self, *, timeout: float) -> None:
            captured["timeout"] = timeout

        async def __aenter__(self) -> FakeAsyncClient:
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

        async def post(self, url: str, *, content: bytes, headers: dict[str, str]) -> FakeResponse:
            captured["url"] = url
            captured["content"] = content.decode("utf-8")
            captured["headers"] = headers
            return FakeResponse()

    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)

    client = WorkdaySoapClient(
        endpoint_url="https://example.test/soap",
        username="u",
        password="p",
        timeout_s=12.0,
    )
    body = await client.call(body_xml="<wd:Request/>", correlation_id="corr-1")

    assert body == "<response/>"
    envelope = captured["content"]
    assert isinstance(envelope, str)
    assert "<wsse:Username>u</wsse:Username>" in envelope
    assert "<wd:Request/>" in envelope
    headers = captured["headers"]
    assert isinstance(headers, dict)
    assert headers["X-Correlation-Id"] == "corr-1"
    assert "Authorization" not in headers


@pytest.mark.asyncio
async def test_soap_call_with_bearer_token(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class FakeResponse:
        status_code = 200
        text = "ok"
        headers: dict[str, str] = {}

        @property
        def request(self) -> object:
            class Req:
                method = "POST"
                url = "https://example.test/soap"

            return Req()

        def raise_for_status(self) -> None:
            return None

    class FakeAsyncClient:
        def __init__(self, *, timeout: float) -> None:
            pass

        async def __aenter__(self) -> FakeAsyncClient:
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

        async def post(self, url: str, *, content: bytes, headers: dict[str, str]) -> FakeResponse:
            captured["headers"] = headers
            captured["content"] = content.decode("utf-8")
            return FakeResponse()

    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)

    client = WorkdaySoapClient(
        endpoint_url="https://example.test/soap",
        bearer_token="access-token",
    )
    await client.call(body_xml="<body/>", soap_action="Get_Things")

    headers = captured["headers"]
    assert isinstance(headers, dict)
    assert headers["Authorization"] == "Bearer access-token"
    assert headers["SOAPAction"] == "Get_Things"
    content = captured["content"]
    assert isinstance(content, str)
    assert "wsse:Security" not in content


@pytest.mark.asyncio
async def test_soap_call_with_oauth(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class FakeOAuth:
        async def headers(self) -> dict[str, str]:
            return {"Authorization": "Bearer oauth-token"}

    class FakeResponse:
        status_code = 200
        text = "ok"
        headers: dict[str, str] = {}

        @property
        def request(self) -> object:
            class Req:
                method = "POST"
                url = "https://example.test/soap"

            return Req()

        def raise_for_status(self) -> None:
            return None

    class FakeAsyncClient:
        def __init__(self, *, timeout: float) -> None:
            pass

        async def __aenter__(self) -> FakeAsyncClient:
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

        async def post(self, url: str, *, content: bytes, headers: dict[str, str]) -> FakeResponse:
            captured["headers"] = headers
            return FakeResponse()

    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)

    client = WorkdaySoapClient(
        endpoint_url="https://example.test/soap",
        oauth=FakeOAuth(),
    )
    await client.call(body_xml="<body/>")

    headers = captured["headers"]
    assert isinstance(headers, dict)
    assert headers["Authorization"] == "Bearer oauth-token"


@pytest.mark.asyncio
async def test_soap_call_rejects_bearer_token_and_oauth_together() -> None:
    client = WorkdaySoapClient(
        endpoint_url="https://example.test/soap",
        bearer_token="t",
        oauth=OAuthRefreshTokenBearerAuth(
            token_url="https://example.test/token",
            client_id="c",
            client_secret="s",
            refresh_token="r",
        ),
    )
    with pytest.raises(WorkdaySoapError, match="at most one"):
        await client.call(body_xml="<body/>")


@pytest.mark.asyncio
async def test_soap_call_redirect_raises_helpful_error(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeResponse:
        status_code = 302
        text = ""
        headers = {"location": "https://example.test/login"}

        @property
        def request(self) -> object:
            class Req:
                method = "POST"
                url = "https://example.test/ui"

            return Req()

        def raise_for_status(self) -> None:
            return None

    class FakeAsyncClient:
        def __init__(self, *, timeout: float) -> None:
            pass

        async def __aenter__(self) -> FakeAsyncClient:
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

        async def post(self, url: str, *, content: bytes, headers: dict[str, str]) -> FakeResponse:
            return FakeResponse()

    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)

    client = WorkdaySoapClient(endpoint_url="https://example.test/ui")
    with pytest.raises(WorkdaySoapError, match="redirect"):
        await client.call(body_xml="<body/>")


@pytest.mark.asyncio
async def test_soap_call_http_401_includes_bearer_hint(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeResponse:
        status_code = 401
        text = "Unauthorized"
        headers = {"www-authenticate": "Bearer realm=workday"}

        @property
        def request(self) -> object:
            class Req:
                method = "POST"
                url = "https://example.test/soap"

            return Req()

        def raise_for_status(self) -> None:
            raise httpx.HTTPStatusError("401", request=self.request, response=self)

    class FakeAsyncClient:
        def __init__(self, *, timeout: float) -> None:
            pass

        async def __aenter__(self) -> FakeAsyncClient:
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

        async def post(self, url: str, *, content: bytes, headers: dict[str, str]) -> FakeResponse:
            return FakeResponse()

    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)

    client = WorkdaySoapClient(
        endpoint_url="https://example.test/soap",
        bearer_token="short",
    )
    with pytest.raises(WorkdaySoapError, match="OAuth access token") as exc_info:
        await client.call(body_xml="<body/>")
    assert "bearer_token" in str(exc_info.value)


@pytest.mark.asyncio
async def test_soap_call_merges_custom_headers(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class FakeResponse:
        status_code = 200
        text = "ok"
        headers: dict[str, str] = {}

        @property
        def request(self) -> object:
            class Req:
                method = "POST"
                url = "https://example.test/soap"

            return Req()

        def raise_for_status(self) -> None:
            return None

    class FakeAsyncClient:
        def __init__(self, *, timeout: float) -> None:
            pass

        async def __aenter__(self) -> FakeAsyncClient:
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

        async def post(self, url: str, *, content: bytes, headers: dict[str, str]) -> FakeResponse:
            captured["headers"] = headers
            return FakeResponse()

    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)

    client = WorkdaySoapClient(endpoint_url="https://example.test/soap")
    await client.call(body_xml="<body/>", headers={"X-Custom": "value"})

    headers = captured["headers"]
    assert isinstance(headers, dict)
    assert headers["X-Custom"] == "value"
