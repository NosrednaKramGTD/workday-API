from __future__ import annotations

import argparse
import os
from collections.abc import Iterable
from dataclasses import dataclass

from app_secrets.json_secrets import JsonSecretManager
from dotenv import load_dotenv


@dataclass(frozen=True)
class RuntimeConfig:
    environment: str
    secrets_file: str


def parse_common_args(argv: Iterable[str] | None = None) -> RuntimeConfig:
    """
    Common CLI flags for examples/scripts.

    Precedence for selecting environment:
    1) --environment (CLI)
    2) WORKDAY_ENVIRONMENT env var
    3) "sandbox" (default)

    Note:
    - `--environment` is intentionally **not** constrained to a fixed set. Any string is allowed,
      so you can define additional sections in `secrets.workday.json` (e.g. "prod_rest",
      "sandbox_student_records", etc.).
    """

    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument(
        "--environment",
        default=None,
        help="Select which environment config to load (overrides all other options).",
    )
    parser.add_argument(
        "--secrets-file",
        default=os.environ.get("WORKDAY_SECRETS_FILE", "secrets.workday.json"),
        help="Path to JSON secrets file (default: secrets.workday.json or WORKDAY_SECRETS_FILE).",
    )

    args, _unknown = parser.parse_known_args(list(argv) if argv is not None else None)

    env = args.environment or os.environ.get("WORKDAY_ENVIRONMENT") or "sandbox"
    return RuntimeConfig(environment=env, secrets_file=args.secrets_file)


def load_settings(
    *,
    environment: str,
    secrets_file: str,
    extra_keys: list[str] | None = None,
) -> None:
    """
    Load settings into process env in this order:

    - `.env` (via python-dotenv) first, as a lightweight local override
    - JSON secrets for the selected environment next

    Final precedence:
    - Existing process env vars win over everything (useful for CI/containers)
    - JSON secrets fill missing keys
    - `.env` fills missing keys
    """

    load_dotenv(override=False)

    manager = JsonSecretManager(secrets_file)

    # The app-secrets interface logs on missing secrets, so keep this list to the
    # "core" keys needed to construct clients. Script/test-specific inputs should
    # be provided via env directly or loaded by that script/test as needed.
    # Keep this list intentionally small to avoid noisy "Secret X not found" logs
    # when a given environment only configures a subset of capabilities (REST-only,
    # SOAP-only, etc.). Individual scripts should request what they need via `extra_keys`.
    core_keys = [
        "WORKDAY_REST_BASE_URL",
        "WORKDAY_TOKEN_URL",
        "WORKDAY_CLIENT_ID",
        "WORKDAY_CLIENT_SECRET",
        "WORKDAY_REFRESH_TOKEN",
    ]

    for key in core_keys + list(extra_keys or []):
        if os.environ.get(key):
            continue
        try:
            value = manager.get_secret(key, environment=environment)
        except ValueError:
            continue
        if value is None:
            continue
        os.environ[key] = str(value)

