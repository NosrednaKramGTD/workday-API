from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from workday_raas.auth import BasicAuth, OAuthRefreshTokenAuth
from workday_raas.client_async import RaasAsyncClient

from .auth import OAuthRefreshTokenBearerAuth
from .rest import BasicRestAuth, WorkdayRestClient
from .soap import WorkdaySoapClient


@dataclass(frozen=True)
class WorkdayApi:
    """
    Opinionated entrypoint for Workday API access.

    Today this is RaaS-first and delegates all HTTP/auth/retry behavior to
    the upstream `workday-raas-client`.
    """

    raas: RaasAsyncClient
    rest: WorkdayRestClient | None = None
    soap: WorkdaySoapClient | None = None

    @staticmethod
    def from_basic(
        username: str,
        password: str,
        *,
        rest_base_url: str | None = None,
        soap_endpoint_url: str | None = None,
        soap_bearer_token: str | None = None,
    ) -> WorkdayApi:
        rest = (
            WorkdayRestClient(
                base_url=rest_base_url,
                auth=BasicRestAuth(username=username, password=password),
            )
            if rest_base_url
            else None
        )
        soap = (
            WorkdaySoapClient(
                endpoint_url=soap_endpoint_url,
                username=username if soap_bearer_token is None else None,
                password=password if soap_bearer_token is None else None,
                bearer_token=soap_bearer_token,
            )
            if soap_endpoint_url
            else None
        )

        return WorkdayApi(
            raas=RaasAsyncClient(auth=BasicAuth(username=username, password=password)),
            rest=rest,
            soap=soap,
        )

    @staticmethod
    def from_oauth_refresh_token(
        *,
        token_url: str,
        client_id: str,
        client_secret: str,
        refresh_token: str,
        scope: str | None = None,
        rest_base_url: str | None = None,
        soap_endpoint_url: str | None = None,
        soap_token_url: str | None = None,
        soap_client_id: str | None = None,
        soap_client_secret: str | None = None,
        soap_refresh_token: str | None = None,
        soap_scope: str | None = None,
    ) -> WorkdayApi:
        auth = OAuthRefreshTokenAuth(
            token_url=token_url,
            client_id=client_id,
            client_secret=client_secret,
            refresh_token=refresh_token,
        )
        soap_oauth: OAuthRefreshTokenBearerAuth | None = None
        if soap_endpoint_url:
            soap_oauth = OAuthRefreshTokenBearerAuth(
                token_url=soap_token_url or token_url,
                client_id=soap_client_id or client_id,
                client_secret=soap_client_secret or client_secret,
                refresh_token=soap_refresh_token or refresh_token,
                scope=soap_scope,
            )
        rest = (
            WorkdayRestClient(
                base_url=rest_base_url,
                auth=OAuthRefreshTokenBearerAuth(
                    token_url=token_url,
                    client_id=client_id,
                    client_secret=client_secret,
                    refresh_token=refresh_token,
                    scope=scope,
                ),
            )
            if rest_base_url
            else None
        )
        soap = (
            WorkdaySoapClient(endpoint_url=soap_endpoint_url, oauth=soap_oauth)
            if soap_endpoint_url and soap_oauth is not None
            else None
        )
        return WorkdayApi(raas=RaasAsyncClient(auth=auth), rest=rest, soap=soap)

    @staticmethod
    def from_env_basic(
        *,
        username_env: str = "WORKDAY_USERNAME",
        password_env: str = "WORKDAY_PASSWORD",
        rest_base_url_env: str = "WORKDAY_REST_BASE_URL",
        soap_endpoint_url_env: str = "WORKDAY_SOAP_ENDPOINT_URL",
        soap_bearer_token_env: str = "WORKDAY_SOAP_BEARER_TOKEN",
    ) -> WorkdayApi:
        username = os.environ[username_env]
        password = os.environ[password_env]
        rest_base_url = os.environ.get(rest_base_url_env)
        soap_endpoint_url = os.environ.get(soap_endpoint_url_env)
        soap_bearer_token = os.environ.get(soap_bearer_token_env)
        return WorkdayApi.from_basic(
            username=username,
            password=password,
            rest_base_url=rest_base_url,
            soap_endpoint_url=soap_endpoint_url,
            soap_bearer_token=soap_bearer_token,
        )

    @staticmethod
    def from_env_oauth_refresh_token(
        *,
        token_url_env: str = "WORKDAY_TOKEN_URL",
        client_id_env: str = "WORKDAY_CLIENT_ID",
        client_secret_env: str = "WORKDAY_CLIENT_SECRET",
        refresh_token_env: str = "WORKDAY_REFRESH_TOKEN",
        scope_env: str = "WORKDAY_REST_SCOPE",
        rest_base_url_env: str = "WORKDAY_REST_BASE_URL",
        soap_endpoint_url_env: str = "WORKDAY_SOAP_ENDPOINT_URL",
        soap_token_url_env: str = "WORKDAY_SOAP_TOKEN_URL",
        soap_client_id_env: str = "WORKDAY_SOAP_CLIENT_ID",
        soap_client_secret_env: str = "WORKDAY_SOAP_CLIENT_SECRET",
        soap_refresh_token_env: str = "WORKDAY_SOAP_REFRESH_TOKEN",
        soap_scope_env: str = "WORKDAY_SOAP_SCOPE",
    ) -> WorkdayApi:
        return WorkdayApi.from_oauth_refresh_token(
            token_url=os.environ[token_url_env],
            client_id=os.environ[client_id_env],
            client_secret=os.environ[client_secret_env],
            refresh_token=os.environ[refresh_token_env],
            scope=os.environ.get(scope_env),
            rest_base_url=os.environ.get(rest_base_url_env),
            soap_endpoint_url=os.environ.get(soap_endpoint_url_env),
            soap_token_url=os.environ.get(soap_token_url_env),
            soap_client_id=os.environ.get(soap_client_id_env),
            soap_client_secret=os.environ.get(soap_client_secret_env),
            soap_refresh_token=os.environ.get(soap_refresh_token_env),
            soap_scope=os.environ.get(soap_scope_env),
        )

    async def run_raas_json(
        self,
        *,
        report_url: str,
        params: Mapping[str, Any] | None = None,
        correlation_id: str | None = None,
    ) -> Any:
        """Convenience wrapper for the most common case: run a RaaS report as JSON."""

        return await self.raas.run_report_parsed(
            report_url=report_url,
            fmt="json",
            params=dict(params or {}),
            correlation_id=correlation_id,
        )
