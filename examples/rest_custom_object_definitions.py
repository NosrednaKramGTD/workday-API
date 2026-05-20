import asyncio
import json
import os
import sys
import time
from typing import Any

from workday_api import WorkdayApi
from workday_api.auth import OAuthRefreshTokenBearerAuth
from workday_api.config import load_settings, parse_common_args
from workday_api.rest import WorkdayRestHttpError


def _as_list(payload: Any) -> list[Any]:
    # Workday endpoints vary: {data:[...]}, {definitions:[...]}, or a bare list.
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("data", "definitions", "items"):
            value = payload.get(key)
            if isinstance(value, list):
                return value
    return []

def _redact(value: str | None) -> str:
    if value is None:
        return "(unset)"
    v = value.strip()
    if not v:
        return "(empty)"
    # Keep enough to correlate which secret is loaded, without leaking it.
    if len(v) <= 8:
        return f"{v[0]}***{v[-1]} (len={len(v)})"
    return f"{v[:4]}***{v[-4:]} (len={len(v)})"


def _print_env_diagnostics() -> None:
    keys = [
        "WORKDAY_REST_BASE_URL",
        "WORKDAY_TOKEN_URL",
        "WORKDAY_CLIENT_ID",
        "WORKDAY_CLIENT_SECRET",
        "WORKDAY_REFRESH_TOKEN",
        "WORKDAY_REST_SCOPE",
        "WORKDAY_CUSTOM_OBJECT_DEFINITION_ID",
    ]
    print("== Workday REST diagnostics (redacted) ==")
    for k in keys:
        print(f"{k}={_redact(os.environ.get(k))}")
    print("========================================")


async def main() -> None:
    """
    Example: list Workday Custom Object Definitions via REST (WCP host).

    Endpoint used (example from your curl):
      GET /customObjectDefinition/v1/definitions

    Requirements (refresh-token pattern):
    - WORKDAY_REST_BASE_URL
        Example: https://api.us.wcp.workday.com
    - WORKDAY_TOKEN_URL
    - WORKDAY_CLIENT_ID
    - WORKDAY_CLIENT_SECRET
    - WORKDAY_REFRESH_TOKEN

    Optional:
    - WORKDAY_CUSTOM_OBJECT_DEFINITION_ID
        If set, also fetches:
          GET /customObjectDefinition/v1/definitions/{id}

    Notes / best practices:
    - Do NOT hardcode access tokens in code or scripts (they expire quickly and are sensitive).
    - Keep the REST host/base URL in `.env` and source it into your shell.
    - If you get HTTP 401/403, see `docs/workday_rest_custom_objects_setup.md`
      for tenant security setup.
    """

    cfg = parse_common_args(sys.argv[1:])
    load_settings(environment=cfg.environment, secrets_file=cfg.secrets_file)

    api = WorkdayApi.from_env_oauth_refresh_token()
    if api.rest is None:
        raise RuntimeError(
            "REST is not configured. Set WORKDAY_REST_BASE_URL and OAuth refresh-token env vars."
        )

    _print_env_diagnostics()
    print(f"REST base URL: {os.environ.get('WORKDAY_REST_BASE_URL')!r}")

    # Prove the refresh-token exchange works (without printing the access token).
    if isinstance(api.rest.auth, OAuthRefreshTokenBearerAuth):
        try:
            token = await api.rest.auth.get_access_token()
            ttl_s = None
            if getattr(api.rest.auth, "_expires_at_s", None):
                ttl_s = int(api.rest.auth._expires_at_s - time.time())
            ttl_text = f"{ttl_s}s" if ttl_s is not None else "(unknown)"
            print(
                "OAuth refresh-token exchange: OK "
                f"(access_token_len={len(token)} expires_in~{ttl_text})"
            )
        except Exception as e:
            print(f"OAuth refresh-token exchange: FAILED ({type(e).__name__}: {e})")
            raise

    correlation_id = "example-rest-custom-object-definitions-001"
    headers = {"accept": "application/json"}

    try:
        definitions = await api.rest.get_json(
            "/customObjectDefinitions",
            headers=headers,
            correlation_id=correlation_id,
        )
    except WorkdayRestHttpError as e:
        print("== REST call failed ==")
        print(f"status_code={e.status_code}")
        print(f"method={e.method}")
        print(f"url={e.url}")
        print(f"correlation_id={e.correlation_id}")
        print(f"sent_bearer_auth={e.sent_bearer_auth}")
        print(f"response_headers={e.response_headers}")
        print("response_body_preview=")
        print(e.response_body_preview or "")
        print("======================")
        raise

    defs_list = _as_list(definitions)
    print(f"Fetched definitions payload type={type(definitions).__name__} count={len(defs_list)}")
    if defs_list:
        preview = defs_list[0]
        if isinstance(preview, dict):
            keys = sorted(preview.keys())
            print(f"First item keys: {keys[:30]}{'...' if len(keys) > 30 else ''}")
        else:
            print(f"First item type: {type(preview).__name__}")

    print("== Definitions response (formatted JSON) ==")
    print(json.dumps(definitions, indent=2, ensure_ascii=False))
    print("============================================")

    definition_id = os.environ.get("WORKDAY_CUSTOM_OBJECT_DEFINITION_ID")
    if definition_id:
        try:
            detail = await api.rest.get_json(
                f"/customObjectDefinition/v1/definitions/{definition_id}",
                headers=headers,
                correlation_id="example-rest-custom-object-definitions-002",
            )
        except WorkdayRestHttpError as e:
            print("== REST detail call failed ==")
            print(f"status_code={e.status_code}")
            print(f"method={e.method}")
            print(f"url={e.url}")
            print(f"correlation_id={e.correlation_id}")
            print(f"sent_bearer_auth={e.sent_bearer_auth}")
            print(f"response_headers={e.response_headers}")
            print("response_body_preview=")
            print(e.response_body_preview or "")
            print("============================")
            raise
        print("== Definition detail (formatted JSON) ==")
        print(json.dumps(detail, indent=2, ensure_ascii=False))
        print("=========================================")


if __name__ == "__main__":
    asyncio.run(main())

