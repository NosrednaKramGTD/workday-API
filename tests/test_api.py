from __future__ import annotations

import pytest

from workday_api.api import WorkdayApi
from workday_api.rest import BasicRestAuth, WorkdayRestClient
from workday_api.soap import WorkdaySoapClient


def test_from_basic_builds_rest_and_soap_clients() -> None:
    api = WorkdayApi.from_basic(
        username="u",
        password="p",
        rest_base_url="https://rest.example/",
        soap_endpoint_url="https://soap.example/",
    )
    assert api.rest is not None
    assert isinstance(api.rest, WorkdayRestClient)
    assert isinstance(api.rest.auth, BasicRestAuth)
    assert api.soap is not None
    assert isinstance(api.soap, WorkdaySoapClient)
    assert api.soap.username == "u"
    assert api.soap.password == "p"


def test_from_basic_soap_bearer_skips_wsse_credentials() -> None:
    api = WorkdayApi.from_basic(
        username="u",
        password="p",
        soap_endpoint_url="https://soap.example/",
        soap_bearer_token="access",
    )
    assert api.soap is not None
    assert api.soap.bearer_token == "access"
    assert api.soap.username is None
    assert api.soap.password is None


def test_from_oauth_refresh_token_builds_soap_oauth_client() -> None:
    api = WorkdayApi.from_oauth_refresh_token(
        token_url="https://example.test/token",
        client_id="cid",
        client_secret="sec",
        refresh_token="rt",
        rest_base_url="https://rest.example/",
        soap_endpoint_url="https://soap.example/",
    )
    assert api.rest is not None
    assert api.soap is not None
    assert api.soap.oauth is not None
    assert api.soap.bearer_token is None


def test_from_env_basic(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WORKDAY_USERNAME", "env-user")
    monkeypatch.setenv("WORKDAY_PASSWORD", "env-pass")
    monkeypatch.setenv("WORKDAY_REST_BASE_URL", "https://rest.example/")
    api = WorkdayApi.from_env_basic()
    assert api.rest is not None
    assert isinstance(api.rest.auth, BasicRestAuth)
    assert api.rest.auth.username == "env-user"


def test_from_env_oauth_refresh_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WORKDAY_TOKEN_URL", "https://example.test/token")
    monkeypatch.setenv("WORKDAY_CLIENT_ID", "cid")
    monkeypatch.setenv("WORKDAY_CLIENT_SECRET", "sec")
    monkeypatch.setenv("WORKDAY_REFRESH_TOKEN", "rt")
    monkeypatch.setenv("WORKDAY_SOAP_ENDPOINT_URL", "https://soap.example/")
    api = WorkdayApi.from_env_oauth_refresh_token()
    assert api.soap is not None
    assert api.soap.oauth is not None


@pytest.mark.asyncio
async def test_run_raas_json_delegates_to_raas_client() -> None:
    captured: dict[str, object] = {}

    class FakeRaas:
        async def run_report_parsed(self, **kwargs: object) -> dict[str, str]:
            captured.update(kwargs)
            return {"rows": []}

    api = WorkdayApi(raas=FakeRaas())  # type: ignore[arg-type]
    result = await api.run_raas_json(
        report_url="https://example.test/report",
        params={"q": "1"},
        correlation_id="corr-raas",
    )
    assert result == {"rows": []}
    assert captured["report_url"] == "https://example.test/report"
    assert captured["fmt"] == "json"
    assert captured["params"] == {"q": "1"}
    assert captured["correlation_id"] == "corr-raas"
