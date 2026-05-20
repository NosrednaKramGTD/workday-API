from __future__ import annotations

import json
import os

import pytest

from workday_api.config import load_settings, parse_common_args


def test_parse_common_args_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("WORKDAY_ENVIRONMENT", raising=False)
    cfg = parse_common_args([])
    assert cfg.environment == "sandbox"
    assert cfg.secrets_file == "secrets.workday.json"


def test_parse_common_args_cli_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WORKDAY_ENVIRONMENT", "ignored")
    cfg = parse_common_args(
        ["--environment", "prod_soap", "--secrets-file", "/tmp/secrets.json"]
    )
    assert cfg.environment == "prod_soap"
    assert cfg.secrets_file == "/tmp/secrets.json"


def test_parse_common_args_env_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WORKDAY_ENVIRONMENT", "preview")
    monkeypatch.setenv("WORKDAY_SECRETS_FILE", "custom.json")
    cfg = parse_common_args([])
    assert cfg.environment == "preview"
    assert cfg.secrets_file == "custom.json"


def test_load_settings_fills_missing_env_from_secrets(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    secrets = {
        "sandbox": {
            "WORKDAY_CLIENT_ID": "cid-from-json",
            "WORKDAY_CLIENT_SECRET": "sec-from-json",
        }
    }
    secrets_file = tmp_path / "secrets.workday.json"
    secrets_file.write_text(json.dumps(secrets), encoding="utf-8")

    for key in (
        "WORKDAY_REST_BASE_URL",
        "WORKDAY_TOKEN_URL",
        "WORKDAY_CLIENT_ID",
        "WORKDAY_CLIENT_SECRET",
        "WORKDAY_REFRESH_TOKEN",
        "WORKDAY_SOAP_ENDPOINT_URL",
    ):
        monkeypatch.delenv(key, raising=False)

    load_settings(environment="sandbox", secrets_file=str(secrets_file))

    assert os.environ["WORKDAY_CLIENT_ID"] == "cid-from-json"
    assert os.environ["WORKDAY_CLIENT_SECRET"] == "sec-from-json"


def test_load_settings_does_not_override_existing_env(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    secrets = {"sandbox": {"WORKDAY_CLIENT_ID": "from-json"}}
    secrets_file = tmp_path / "secrets.workday.json"
    secrets_file.write_text(json.dumps(secrets), encoding="utf-8")

    monkeypatch.setenv("WORKDAY_CLIENT_ID", "from-env")
    load_settings(environment="sandbox", secrets_file=str(secrets_file))
    assert os.environ["WORKDAY_CLIENT_ID"] == "from-env"


def test_load_settings_extra_keys(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    secrets = {"sandbox": {"WORKDAY_SOAP_ENDPOINT_URL": "https://soap.example/endpoint"}}
    secrets_file = tmp_path / "secrets.workday.json"
    secrets_file.write_text(json.dumps(secrets), encoding="utf-8")

    monkeypatch.delenv("WORKDAY_SOAP_ENDPOINT_URL", raising=False)
    load_settings(
        environment="sandbox",
        secrets_file=str(secrets_file),
        extra_keys=["WORKDAY_SOAP_ENDPOINT_URL"],
    )
    assert os.environ["WORKDAY_SOAP_ENDPOINT_URL"] == "https://soap.example/endpoint"
