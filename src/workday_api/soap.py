from __future__ import annotations

from collections.abc import Mapping, MutableMapping
from dataclasses import dataclass
from typing import TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    from .auth import HeaderAuth


class WorkdaySoapError(RuntimeError):
    pass


def _soap_envelope(*, body_xml: str, wsse_header_xml: str | None) -> str:
    header = wsse_header_xml or ""
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/">'
        f"<soapenv:Header>{header}</soapenv:Header>"
        f"<soapenv:Body>{body_xml}</soapenv:Body>"
        "</soapenv:Envelope>"
    )


def wsse_username_token_header(*, username: str, password: str) -> str:
    # Workday SOAP commonly accepts WS-Security UsernameToken.
    # (Nonce/Created can be added later if required by your tenant/policy.)
    return (
        '<wsse:Security xmlns:wsse="http://docs.oasis-open.org/wss/2004/01/'
        'oasis-200401-wss-wssecurity-secext-1.0.xsd">'
        "<wsse:UsernameToken>"
        f"<wsse:Username>{_xml_escape(username)}</wsse:Username>"
        f"<wsse:Password>{_xml_escape(password)}</wsse:Password>"
        "</wsse:UsernameToken>"
        "</wsse:Security>"
    )


def _xml_escape(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


@dataclass(frozen=True)
class WorkdaySoapClient:
    """
    Minimal async SOAP client for Workday.

    - Builds a SOAP 1.1 envelope
    - Supports WS-Security UsernameToken header (legacy / on-prem style)
    - Or OAuth2 bearer via `bearer_token` or `oauth` (WCP / api.*.wcp.workday.com style)
    - Sends via HTTP POST
    """

    endpoint_url: str
    username: str | None = None
    password: str | None = None
    bearer_token: str | None = None
    oauth: HeaderAuth | None = None
    timeout_s: float = 60.0

    async def call(
        self,
        *,
        body_xml: str,
        soap_action: str | None = None,
        headers: Mapping[str, str] | None = None,
        correlation_id: str | None = None,
    ) -> str:
        merged_headers: MutableMapping[str, str] = {
            "Content-Type": "text/xml; charset=utf-8",
        }
        if soap_action:
            merged_headers["SOAPAction"] = soap_action
        if correlation_id:
            merged_headers.setdefault("X-Correlation-Id", correlation_id)
        if headers:
            merged_headers.update(headers)

        if self.bearer_token is not None and self.oauth is not None:
            raise WorkdaySoapError("Set at most one of bearer_token and oauth on WorkdaySoapClient")

        auth_mode = "none"
        if self.bearer_token is not None:
            merged_headers["Authorization"] = f"Bearer {self.bearer_token}"
            wsse = None
            auth_mode = "bearer_token"
        elif self.oauth is not None:
            merged_headers.update(await self.oauth.headers())
            wsse = None
            auth_mode = "oauth_refresh_token"
        else:
            wsse = None
            if self.username is not None and self.password is not None:
                wsse = wsse_username_token_header(username=self.username, password=self.password)
                auth_mode = "wsse_username_token"

        envelope = _soap_envelope(body_xml=body_xml, wsse_header_xml=wsse)

        async with httpx.AsyncClient(timeout=self.timeout_s) as client:
            resp = await client.post(
                self.endpoint_url,
                content=envelope.encode("utf-8"),
                headers=merged_headers,
            )
            if 300 <= resp.status_code < 400:
                location = resp.headers.get("location")
                raise WorkdaySoapError(
                    "Workday SOAP endpoint returned a redirect, which usually means you are "
                    "hitting a UI URL, not the SOAP service endpoint.\n"
                    f"HTTP {resp.status_code} for {resp.request.method} {resp.request.url}\n"
                    f"Location: {location}\n"
                    "Tip: use your tenant's SOAP WSDL URL (often ends with `?wsdl`) and set "
                    "`WORKDAY_SOAP_ENDPOINT_URL` to the same URL *without* `?wsdl`."
                )
            try:
                resp.raise_for_status()
            except httpx.HTTPStatusError as e:
                # Workday frequently returns a useful SOAP Fault body even with 500s.
                body_snippet = (resp.text or "")[:8000]
                hint = ""
                www_auth = resp.headers.get("www-authenticate", "").lower()
                if resp.status_code == 401 and www_auth.startswith("bearer"):
                    auth_header = merged_headers.get("Authorization")
                    auth_summary = (
                        "missing"
                        if not auth_header
                        else f"present (len={len(auth_header)} prefix={auth_header[:16]!r})"
                    )
                    hint = (
                        "\nHint: this endpoint expects an OAuth access token in "
                        "Authorization: Bearer … (not your refresh token, not WS-Security "
                        "password alone). Use WorkdayApi.from_env_oauth_refresh_token() or set "
                        "WORKDAY_SOAP_BEARER_TOKEN to a freshly minted access_token from your "
                        "token endpoint.\n"
                        f"Auth mode used: {auth_mode}. Authorization header: {auth_summary}\n"
                    )
                raise WorkdaySoapError(
                    "Workday SOAP call failed: "
                    f"HTTP {resp.status_code} for {resp.request.method} {resp.request.url}\n"
                    f"Response headers: {dict(resp.headers)}\n"
                    f"Response body (first 8000 chars):\n{body_snippet}{hint}"
                ) from e

            return resp.text

