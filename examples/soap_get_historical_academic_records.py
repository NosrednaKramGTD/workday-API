import asyncio
import os
import sys

from workday_api import WorkdayApi
from workday_api.config import load_settings, parse_common_args
from workday_api.xml_debug import print_xml


def _env(name: str) -> str | None:
    value = os.environ.get(name)
    return value if value and value.strip() else None


async def main() -> None:
    """
    Requirements:
    - WORKDAY_SOAP_ENDPOINT_URL
    - Either:
      - WORKDAY_SOAP_BEARER_TOKEN (a short-lived OAuth access_token), or
      - OAuth refresh-token env vars:
        - WORKDAY_TOKEN_URL
        - WORKDAY_CLIENT_ID
        - WORKDAY_CLIENT_SECRET
        - WORKDAY_REFRESH_TOKEN
    - WORKDAY_INSTITUTION_ACADEMIC_UNIT_ID (required by Get_Historical_Academic_Records)

    Notes:
    - For WCP SOAP endpoints (e.g. https://api.*.wcp.workday.com/soap/...), Workday expects
      Authorization: Bearer <access_token>, which this example obtains via refresh-token exchange.
    """

    cfg = parse_common_args(sys.argv[1:])
    load_settings(
        environment=cfg.environment,
        secrets_file=cfg.secrets_file,
        extra_keys=[
            "WORKDAY_SOAP_ENDPOINT_URL",
            "WORKDAY_SOAP_BEARER_TOKEN",
            "WORKDAY_SOAP_TOKEN_URL",
            "WORKDAY_SOAP_CLIENT_ID",
            "WORKDAY_SOAP_CLIENT_SECRET",
            "WORKDAY_SOAP_REFRESH_TOKEN",
            "WORKDAY_INSTITUTION_ACADEMIC_UNIT_ID",
            "WORKDAY_HISTORICAL_ACADEMIC_RECORD_WID",
        ],
    )

    # Prefer an explicitly provided short-lived access token if present.
    # Otherwise, fall back to refresh-token exchange.
    if os.environ.get("WORKDAY_SOAP_BEARER_TOKEN"):
        api = WorkdayApi.from_env_basic()
    else:
        api = WorkdayApi.from_env_oauth_refresh_token()
    if api.soap is None:
        raise RuntimeError(
            "SOAP is not configured.\n"
            "Set WORKDAY_SOAP_ENDPOINT_URL and either:\n"
            "- WORKDAY_SOAP_BEARER_TOKEN (access_token), or\n"
            "- WORKDAY_TOKEN_URL/WORKDAY_CLIENT_ID/WORKDAY_CLIENT_SECRET/"
            "WORKDAY_REFRESH_TOKEN (refresh-token flow)."
        )

    # Optional: request a single historical academic record by WID.
    record_wid = _env("WORKDAY_HISTORICAL_ACADEMIC_RECORD_WID")
    institution_academic_unit_id = _env("WORKDAY_INSTITUTION_ACADEMIC_UNIT_ID")
    if record_wid is None and institution_academic_unit_id is None:
        raise RuntimeError(
            "Set at least one of:\n"
            "- WORKDAY_HISTORICAL_ACADEMIC_RECORD_WID (fetch a specific record), or\n"
            "- WORKDAY_INSTITUTION_ACADEMIC_UNIT_ID (contextual security scope)\n"
            "Either can be provided via secrets.workday.json for the selected --environment."
        )

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

    body_xml = (
        f"""
<bsvc:Get_Historical_Academic_Records_Request xmlns:bsvc="urn:com.workday/bsvc">
  {request_references_xml}
  {request_criteria_xml}
  <bsvc:Response_Filter>
    <bsvc:Page>1</bsvc:Page>
    <bsvc:Count>10</bsvc:Count>
  </bsvc:Response_Filter>
</bsvc:Get_Historical_Academic_Records_Request>
        """.strip()
    )

    # Often optional for Workday; set if your tenant requires it.
    soap_action = None

    xml = await api.soap.call(
        body_xml=body_xml,
        soap_action=soap_action,
        correlation_id="example-soap-historical-academic-records-001",
    )

    print_xml(
        xml,
        header="== SOAP response (formatted XML) ==",
        footer="===================================",
    )


if __name__ == "__main__":
    asyncio.run(main())

