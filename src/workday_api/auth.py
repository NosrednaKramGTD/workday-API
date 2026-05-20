from __future__ import annotations

import time
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol

import httpx


class HeaderAuth(Protocol):
    async def headers(self) -> Mapping[str, str]: ...


@dataclass
class OAuthRefreshTokenBearerAuth:
    """
    Minimal OAuth2 refresh-token bearer auth for Workday APIs.

    - Exchanges refresh_token -> access_token via the tenant token endpoint
    - Caches access tokens in-memory until close to expiry

    This is intentionally small and dependency-free (other than httpx).
    """

    token_url: str
    client_id: str
    client_secret: str
    refresh_token: str
    scope: str | None = None

    _access_token: str | None = None
    _expires_at_s: float | None = None

    async def headers(self) -> Mapping[str, str]:
        token = await self.get_access_token()
        return {"Authorization": f"Bearer {token}"}

    async def get_access_token(self) -> str:
        now = time.time()
        if self._access_token and self._expires_at_s and now < (self._expires_at_s - 30):
            return self._access_token

        data: dict[str, str] = {
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }
        if self.scope:
            data["scope"] = self.scope

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(self.token_url, data=data)
            try:
                resp.raise_for_status()
            except httpx.HTTPStatusError as e:
                body_preview = (resp.text or "")[:2000]
                hint = ""
                if resp.status_code == 404:
                    hint = (
                        " This usually means WORKDAY_TOKEN_URL points at the wrong host/path "
                        "(copy the Token Endpoint URL from your registered API client's "
                        "OAuth configuration)."
                    )
                raise ValueError(
                    "OAuth token request failed: "
                    f"HTTP {resp.status_code} for POST {self.token_url}.{hint}\n"
                    f"Response body (first 2000 chars):\n{body_preview}"
                ) from e

            payload = resp.json()

        access_token = payload.get("access_token")
        if not access_token:
            raise ValueError("OAuth token response missing access_token")

        expires_in = payload.get("expires_in")
        try:
            expires_in_s = float(expires_in) if expires_in is not None else 3600.0
        except (TypeError, ValueError):
            expires_in_s = 3600.0

        self._access_token = access_token
        self._expires_at_s = now + expires_in_s
        return access_token

