from __future__ import annotations

from collections.abc import Mapping, MutableMapping
from dataclasses import dataclass
from typing import Any

import httpx

from .auth import HeaderAuth


class WorkdayRestHttpError(RuntimeError):
    def __init__(
        self,
        *,
        message: str,
        status_code: int | None = None,
        method: str | None = None,
        url: str | None = None,
        correlation_id: str | None = None,
        response_headers: Mapping[str, str] | None = None,
        response_body_preview: str | None = None,
        sent_bearer_auth: bool | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.method = method
        self.url = url
        self.correlation_id = correlation_id
        self.response_headers = dict(response_headers or {})
        self.response_body_preview = response_body_preview
        self.sent_bearer_auth = sent_bearer_auth


def _safe_error_headers(headers: httpx.Headers) -> dict[str, str]:
    """
    Only include a small allowlist of headers that help debugging.
    Avoid echoing cookies or auth-related headers into exception messages.
    """

    allow = {
        "content-type",
        "date",
        "server",
        "x-correlation-id",
        "x-request-id",
        "x-trace-id",
        "x-amzn-trace-id",
        "x-workday-request-id",
        "x-workday-transaction-id",
        "x-wd-request-id",
        "retry-after",
        "www-authenticate",
    }
    out: dict[str, str] = {}
    for k, v in headers.items():
        lk = k.lower()
        if lk in allow:
            out[k] = v
    return out


def _response_body_preview(resp: httpx.Response, *, limit: int = 4000) -> str:
    content_type = (resp.headers.get("content-type") or "").lower()
    if "application/json" in content_type:
        try:
            payload = resp.json()
            text = str(payload)
            return text[:limit]
        except Exception:
            pass
    try:
        return (resp.text or "")[:limit]
    except Exception:
        return ""


@dataclass
class BasicRestAuth:
    username: str
    password: str

    async def headers(self) -> Mapping[str, str]:
        # httpx will build the header from auth=...; we keep this for symmetry.
        return {}


@dataclass(frozen=True)
class WorkdayRestClient:
    """
    Small async REST client wrapper with:
    - base_url joining
    - optional Basic or OAuth bearer auth
    - correlation id propagation
    """

    base_url: str
    auth: HeaderAuth | BasicRestAuth | None = None
    timeout_s: float = 60.0
    default_headers: Mapping[str, str] | None = None

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        json: Any | None = None,
        data: Any | None = None,
        headers: Mapping[str, str] | None = None,
        correlation_id: str | None = None,
    ) -> httpx.Response:
        merged_headers: MutableMapping[str, str] = {}
        if self.default_headers:
            merged_headers.update(self.default_headers)
        if headers:
            merged_headers.update(headers)
        if correlation_id:
            merged_headers.setdefault("X-Correlation-Id", correlation_id)

        auth = None
        sent_bearer_auth = False
        if isinstance(self.auth, BasicRestAuth):
            auth = (self.auth.username, self.auth.password)
        elif self.auth is not None:
            merged_headers.update(await self.auth.headers())
            auth_header = (
                merged_headers.get("Authorization") or merged_headers.get("authorization") or ""
            )
            sent_bearer_auth = auth_header.lower().startswith("bearer ")

        async with httpx.AsyncClient(base_url=self.base_url, timeout=self.timeout_s) as client:
            resp = await client.request(
                method=method,
                url=path,
                params=dict(params or {}),
                json=json,
                data=data,
                headers=merged_headers,
                auth=auth,
            )
            try:
                resp.raise_for_status()
            except httpx.HTTPStatusError as e:
                url = str(getattr(resp.request, "url", "") or "")

                hints: list[str] = []
                # Common misconfig: using a RaaS host for REST calls.
                if (
                    "/ccx/service/customreport2/" in (self.base_url or "")
                    or "/ccx/service/customreport2/" in url
                ):
                    hints.append(
                        "This looks like a RaaS/customreport2 host. For Workday REST APIs "
                        "(including many Custom Objects endpoints), WORKDAY_REST_BASE_URL is "
                        "typically a REST API base like `https://api.{region}.wcp.workday.com` "
                        "or a tenant REST base under `/ccx/api/...`, not a "
                        "`/ccx/service/customreport2/...` URL."
                    )
                # Another common misconfig: including a service/version segment in base_url.
                if "/v" in (self.base_url or "") and "/ccx/api/" in (self.base_url or ""):
                    hints.append(
                        "Your WORKDAY_REST_BASE_URL includes a `/vXX.X` version segment. "
                        "Usually the version belongs to a *specific service path*, not the base. "
                        "Consider using the base up to `/ccx/api/v1/{tenant}` and keep endpoint "
                        "versions in the request path."
                    )

                hdrs = _safe_error_headers(resp.headers)
                preview = _response_body_preview(resp)
                # Workday sometimes responds with "not found: <service>" when the REST
                # gateway doesn't recognize the service root at this host/base.
                preview_lower = preview.lower()
                if resp.status_code == 404 and "not found: customobjectdefinition" in preview_lower:
                    hints.append(
                        "The REST gateway for this base URL doesn't recognize the "
                        "`customObjectDefinition` service. Double-check WORKDAY_REST_BASE_URL. "
                        "Common working bases are either the WCP host "
                        "(`https://api.{region}.wcp.workday.com`) or a tenant-scoped REST base "
                        "like `https://{cluster}/ccx/api/v1/{tenant}`. If your tenant uses a "
                        "different REST gateway host, use that host as the base and keep "
                        "`/customObjectDefinition/v1/...` in the request path."
                    )
                hint_text = ("\nHints:\n- " + "\n- ".join(hints)) if hints else ""
                message = (
                    "Workday REST request failed: "
                    f"HTTP {resp.status_code} for {method.upper()} {url}.\n"
                    f"Correlation ID: {correlation_id or '(none)'}\n"
                    f"Sent Bearer auth: {sent_bearer_auth}\n"
                    f"Response headers (subset): {hdrs}\n"
                    f"Response body preview (first {len(preview)} chars):\n{preview}"
                    f"{hint_text}"
                )
                raise WorkdayRestHttpError(
                    message=message,
                    status_code=resp.status_code,
                    method=method.upper(),
                    url=url,
                    correlation_id=correlation_id,
                    response_headers=hdrs,
                    response_body_preview=preview,
                    sent_bearer_auth=sent_bearer_auth,
                ) from e
            return resp

    async def get_json(
        self,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
        correlation_id: str | None = None,
    ) -> Any:
        resp = await self.request(
            "GET",
            path,
            params=params,
            headers=headers,
            correlation_id=correlation_id,
        )
        return resp.json()

