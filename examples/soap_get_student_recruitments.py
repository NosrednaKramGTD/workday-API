import asyncio
import os
import sys

from workday_api import WorkdayApi
from workday_api.config import load_settings, parse_common_args
from workday_api.xml_debug import print_xml


def _env(name: str) -> str | None:
    value = os.environ.get(name)
    return value if value and value.strip() else None


def _xml_bool(value: bool) -> str:
    return "true" if value else "false"


def _include_tag(local_name: str, *, value: bool) -> str:
    return f"    <bsvc:{local_name}>{_xml_bool(value)}</bsvc:{local_name}>"


def _env_bool(name: str, *, default: bool) -> bool:
    value = _env(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


async def main() -> None:
    """
    Call Get_Student_Recruitments on Student_Recruiting v46.0.

    Requirements:
    - WORKDAY_SOAP_ENDPOINT_URL (e.g. .../western/Student_Recruiting/v46.0)
    - Either:
      - WORKDAY_SOAP_BEARER_TOKEN (a short-lived OAuth access_token), or
      - OAuth refresh-token env vars, or
      - WORKDAY_USERNAME / WORKDAY_PASSWORD (WS-Security UsernameToken)
    - WORKDAY_STUDENT_RECRUITMENT_WID (Student_Recruitment_Reference WID)

    Optional:
    - WORKDAY_AS_OF_EFFECTIVE_DATE (Response_Filter)
    - WORKDAY_AS_OF_ENTRY_DATETIME (Response_Filter)
    - WORKDAY_INCLUDE_* booleans for Response_Group (see script body)

    Run:
      uv run python examples/soap_get_student_recruitments.py --environment prod_soap
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
            "WORKDAY_USERNAME",
            "WORKDAY_PASSWORD",
            "WORKDAY_STUDENT_RECRUITMENT_WID",
            "WORKDAY_AS_OF_EFFECTIVE_DATE",
            "WORKDAY_AS_OF_ENTRY_DATETIME",
        ],
    )

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
            "WORKDAY_REFRESH_TOKEN, or\n"
            "- WORKDAY_USERNAME/WORKDAY_PASSWORD (WS-Security)."
        )

    recruitment_wid = _env("WORKDAY_STUDENT_RECRUITMENT_WID")
    if recruitment_wid is None:
        raise RuntimeError(
            "Set WORKDAY_STUDENT_RECRUITMENT_WID (Student_Recruitment_Reference WID).\n"
            "It can be provided via secrets.workday.json for the selected --environment."
        )

    as_of_effective_date = _env("WORKDAY_AS_OF_EFFECTIVE_DATE") or "2024-01-01"
    as_of_entry_datetime = _env("WORKDAY_AS_OF_ENTRY_DATETIME") or "2024-01-01T08:00:01Z"

    include_reference = _env_bool("WORKDAY_INCLUDE_REFERENCE", default=False)
    include_person_data = _env_bool("WORKDAY_INCLUDE_PERSON_DATA", default=False)
    include_personal_portfolio_data = _env_bool(
        "WORKDAY_INCLUDE_PERSONAL_PORTFOLIO_DATA", default=False
    )
    include_school_data = _env_bool("WORKDAY_INCLUDE_SCHOOL_DATA", default=False)
    include_friends_and_family_data = _env_bool(
        "WORKDAY_INCLUDE_FRIENDS_AND_FAMILY_DATA", default=False
    )
    include_additional_data_in_response = _env_bool(
        "WORKDAY_INCLUDE_ADDITIONAL_DATA_IN_RESPONSE", default=True
    )

    response_group = "\n".join(
        [
            _include_tag("Include_Reference", value=include_reference),
            _include_tag("Include_Person_Data", value=include_person_data),
            _include_tag(
                "Include_Personal_Portfolio_Data",
                value=include_personal_portfolio_data,
            ),
            _include_tag("Include_School_Data", value=include_school_data),
            _include_tag(
                "Include_Friends_and_Family_Data",
                value=include_friends_and_family_data,
            ),
            _include_tag(
                "Include_Additional_Data_In_Response",
                value=include_additional_data_in_response,
            ),
        ]
    )

    body_xml = f"""
<bsvc:Get_Student_Recruitments_Request xmlns:bsvc="urn:com.workday/bsvc">
  <bsvc:Request_References>
    <bsvc:Student_Recruitment_Reference>
      <bsvc:ID bsvc:type="WID">{recruitment_wid}</bsvc:ID>
    </bsvc:Student_Recruitment_Reference>
  </bsvc:Request_References>
  <bsvc:Response_Filter>
    <bsvc:As_Of_Effective_Date>{as_of_effective_date}</bsvc:As_Of_Effective_Date>
    <bsvc:As_Of_Entry_DateTime>{as_of_entry_datetime}</bsvc:As_Of_Entry_DateTime>
  </bsvc:Response_Filter>
  <bsvc:Response_Group>
{response_group}
  </bsvc:Response_Group>
</bsvc:Get_Student_Recruitments_Request>
    """.strip()

    soap_action = None

    xml = await api.soap.call(
        body_xml=body_xml,
        soap_action=soap_action,
        correlation_id="example-soap-get-student-recruitments-001",
    )

    print_xml(
        xml,
        header="== SOAP response (formatted XML) ==",
        footer="===================================",
    )


if __name__ == "__main__":
    asyncio.run(main())
