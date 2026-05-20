from __future__ import annotations

import os

import pytest

from workday_api import WorkdayApi
from workday_api.auth import OAuthRefreshTokenBearerAuth
from workday_api.config import load_settings


def _env(name: str) -> str | None:
    value = os.environ.get(name)
    return value if value and value.strip() else None


def _root_tag(xml: str) -> str:
    s = xml.lstrip()
    if s.startswith("<?xml"):
        idx = s.find("?>")
        if idx != -1:
            s = s[idx + 2 :].lstrip()
    if not s.startswith("<"):
        return "unknown"
    end = s.find(">")
    if end == -1:
        return "unknown"
    inside = s[1:end].strip()
    return (inside.split()[0] if inside else "unknown").strip()


def _student_records_get_historical_academic_records_body_xml(
    *, institution_academic_unit_id: str | None, record_wid: str | None
) -> str:
    request_references_xml = (
        f"""
        <bsvc:Request_References>
          <bsvc:Historical_Academic_Record_Reference>
            <bsvc:ID bsvc:type="WID">{record_wid}</bsvc:ID>
          </bsvc:Historical_Academic_Record_Reference>
        </bsvc:Request_References>
        """.strip()
        if record_wid
        else ""
    )

    request_criteria_xml = (
        f"""
  <bsvc:Request_Criteria>
    <bsvc:Institution_Reference>
      <bsvc:ID bsvc:type="Academic_Unit_ID">{institution_academic_unit_id}</bsvc:ID>
    </bsvc:Institution_Reference>
  </bsvc:Request_Criteria>
        """.strip()
        if institution_academic_unit_id
        else ""
    )

    return (
        f"""
<bsvc:Get_Historical_Academic_Records_Request xmlns:bsvc="urn:com.workday/bsvc">
  {request_references_xml}
  {request_criteria_xml}
  <bsvc:Response_Filter>
    <bsvc:Page>1</bsvc:Page>
    <bsvc:Count>1</bsvc:Count>
  </bsvc:Response_Filter>
</bsvc:Get_Historical_Academic_Records_Request>
        """.strip()
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_soap_oauth_refresh_token_end_to_end() -> None:
    """
    End-to-end SOAP auth test:

    - Loads config for WORKDAY_ENVIRONMENT from JSON secrets (WORKDAY_SECRETS_FILE)
    - Exchanges refresh_token -> access_token via WORKDAY_TOKEN_URL
    - Makes a real SOAP call to WORKDAY_SOAP_ENDPOINT_URL using Authorization: Bearer ...

    To run:
      uv run pytest -m integration -k soap_oauth_refresh_token_end_to_end

    Required env/secrets keys:
    - WORKDAY_SECRETS_FILE (or default secrets.workday.json)
    - WORKDAY_ENVIRONMENT (prod|sandbox|preview) [optional; defaults to sandbox]
    - WORKDAY_TOKEN_URL
    - WORKDAY_CLIENT_ID
    - WORKDAY_CLIENT_SECRET
    - WORKDAY_REFRESH_TOKEN
    - WORKDAY_SOAP_ENDPOINT_URL

    SOAP request body selection:
    - If WORKDAY_SOAP_E2E_BODY_XML is set, we use it as-is.
    - Otherwise, if WORKDAY_INSTITUTION_ACADEMIC_UNIT_ID is set, we generate a
      Student_Records request: Get_Historical_Academic_Records_Request.

    Optional:
    - WORKDAY_SOAP_E2E_SOAP_ACTION
    - WORKDAY_SOAP_E2E_ASSERT_CONTAINS (substring to assert in the response)
    """

    environment = os.environ.get("WORKDAY_ENVIRONMENT", "sandbox")
    secrets_file = os.environ.get("WORKDAY_SECRETS_FILE", "secrets.workday.json")
    load_settings(environment=environment, secrets_file=secrets_file)

    body_xml = _env("WORKDAY_SOAP_E2E_BODY_XML")
    if body_xml is None:
        record_wid = _env("WORKDAY_HISTORICAL_ACADEMIC_RECORD_WID")
        institution_id = _env("WORKDAY_INSTITUTION_ACADEMIC_UNIT_ID")
        if record_wid is None and institution_id is None:
            pytest.skip(
                "Set WORKDAY_SOAP_E2E_BODY_XML, or set at least one of:\n"
                "- WORKDAY_HISTORICAL_ACADEMIC_RECORD_WID (Request_References), or\n"
                "- WORKDAY_INSTITUTION_ACADEMIC_UNIT_ID (Request_Criteria / contextual scope)\n"
                "to auto-generate a Student_Records Get_Historical_Academic_Records_Request body."
            )
        body_xml = _student_records_get_historical_academic_records_body_xml(
            institution_academic_unit_id=institution_id,
            record_wid=record_wid,
        )

    soap_action = _env("WORKDAY_SOAP_E2E_SOAP_ACTION")
    expected_substring = _env("WORKDAY_SOAP_E2E_ASSERT_CONTAINS")

    # Explicitly prove we can mint an access token.
    bearer = OAuthRefreshTokenBearerAuth(
        token_url=os.environ["WORKDAY_TOKEN_URL"],
        client_id=os.environ["WORKDAY_CLIENT_ID"],
        client_secret=os.environ["WORKDAY_CLIENT_SECRET"],
        refresh_token=os.environ["WORKDAY_REFRESH_TOKEN"],
    )
    access_token = await bearer.get_access_token()
    assert isinstance(access_token, str) and len(access_token) > 20

    # Then make a real SOAP call using the same refresh-token credentials via WorkdayApi wiring.
    api = WorkdayApi.from_env_oauth_refresh_token()
    if api.soap is None:
        pytest.skip("WORKDAY_SOAP_ENDPOINT_URL not set; SOAP client not configured.")

    try:
        resp_xml = await api.soap.call(
            body_xml=body_xml,
            soap_action=soap_action,
            correlation_id="test-soap-oauth-e2e-001",
        )
    except Exception as e:
        raise type(e)(
            f"{e}\n\nE2E request context:\n"
            f"- endpoint: {api.soap.endpoint_url}\n"
            f"- request_root: {_root_tag(body_xml)}\n"
            f"- soap_action: {soap_action!r}\n"
        ) from e

    assert isinstance(resp_xml, str)
    assert resp_xml.strip() != ""
    if expected_substring is not None:
        assert expected_substring in resp_xml

