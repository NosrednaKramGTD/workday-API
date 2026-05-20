from __future__ import annotations

import os

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--environment",
        action="store",
        default=None,
        help=(
            "Select environment for integration tests (sets WORKDAY_ENVIRONMENT). "
            "Any key from secrets.workday.json works (e.g. prod_rest, sandbox_soap)."
        ),
    )
    parser.addoption(
        "--secrets-file",
        action="store",
        default=None,
        help="Path to JSON secrets file for integration tests (sets WORKDAY_SECRETS_FILE).",
    )


def pytest_configure(config: pytest.Config) -> None:
    env = config.getoption("--environment")
    if env:
        os.environ["WORKDAY_ENVIRONMENT"] = env

    secrets_file = config.getoption("--secrets-file")
    if secrets_file:
        os.environ["WORKDAY_SECRETS_FILE"] = secrets_file

