## workday-api
 
A small, **best-practice wrapper** around [`workday-raas-client`](https://github.com/NosrednaKramGTD/workday-raas-client) to make Workday API calls fast and consistent in Python:

- RaaS (reports) via `workday-raas-client`
- REST via `httpx` (Basic or OAuth refresh-token bearer)
- SOAP via `httpx` (SOAP 1.1 envelope + WS-Security UsernameToken)
 
 ### Goals
 
 - **Simple**: one client, a couple of high-level methods
 - **Production-friendly**: async-first, correlation IDs, clear config surface
 - **Compatible**: delegates all Workday RaaS mechanics to `workday-raas-client`
 
### Module layout

- `workday_api.api`: high-level `WorkdayApi` façade (RaaS + optional REST/SOAP)
- `workday_api.rest`: `WorkdayRestClient`
- `workday_api.soap`: `WorkdaySoapClient` + SOAP helpers
- `workday_api.auth`: shared authorization utilities (e.g. refresh-token → bearer)

 ### Install (uv)
 
 ```bash
 uv sync
 ```
 
If you prefer an activated venv (optional):

```bash
source .venv/bin/activate
```

 If you want streaming to StorageKit (depends on your environment):
 
 ```bash
 uv sync --extra storage
 ```
 
 ### Quickstart
 
 ```python
 import asyncio
 from workday_api import WorkdayApi
 
 async def main() -> None:
     api = WorkdayApi.from_env_basic()
 
     data = await api.raas.run_report_parsed(
         report_url="https://wd2-impl-services1.workday.com/ccx/service/customreport2/mytenant/ISU/my_report",
         fmt="json",
         params={"Last_Updated": "2026-03-01"},
         correlation_id="job-001",
     )
     print(type(data), "items" if hasattr(data, "__len__") else "")
 
 asyncio.run(main())
 ```
 
 ### Environment variables
 
 - **Basic auth**
   - `WORKDAY_USERNAME`
   - `WORKDAY_PASSWORD`
   - `WORKDAY_REST_BASE_URL` (optional; enables `api.rest`)
   - `WORKDAY_SOAP_ENDPOINT_URL` (optional; enables `api.soap`)
   - `WORKDAY_SOAP_BEARER_TOKEN` (optional; **required for some endpoints** like `https://api.*.wcp.workday.com/...` that respond with `WWW-Authenticate: Bearer`)
   - For legacy SOAP hosts, this package sends **WS-Security UsernameToken** using `WORKDAY_USERNAME` / `WORKDAY_PASSWORD` unless `WORKDAY_SOAP_BEARER_TOKEN` is set.
   - This must be a **tenant-specific SOAP endpoint**. If you set it to the bare `.../ccx/service/bsvc` you will typically get a SOAP Fault like “Service unavailable”.
   - Common patterns (vary by tenant/service):
     - `https://{cluster}/ccx/service/{tenant}/bsvc`
     - `https://{cluster}/ccx/service/{tenant}/{service}/v{version}`
     - `https://api.{region}.wcp.workday.com/soap/v{version}/{Service_Name}` (often **OAuth bearer**, not WS-Security)
 
 - **OAuth refresh token**
   - `WORKDAY_TOKEN_URL` (must be the **Token Endpoint** from your API client; if this is wrong you will see **HTTP 404** on the token POST)
   - `WORKDAY_CLIENT_ID`
   - `WORKDAY_CLIENT_SECRET`
   - `WORKDAY_REFRESH_TOKEN`
   - `WORKDAY_REST_BASE_URL` (optional; enables `api.rest`)
   - `WORKDAY_SOAP_ENDPOINT_URL` (optional; enables `api.soap` with **OAuth bearer** using the same refresh-token credentials as RaaS/REST)
   - Optional overrides when SOAP uses different OAuth client credentials than RaaS:
     - `WORKDAY_SOAP_TOKEN_URL`
     - `WORKDAY_SOAP_CLIENT_ID`
     - `WORKDAY_SOAP_CLIENT_SECRET`
     - `WORKDAY_SOAP_REFRESH_TOKEN`

### REST example

```python
import asyncio
from workday_api import WorkdayApi

async def main() -> None:
    api = WorkdayApi.from_env_oauth_refresh_token()
    assert api.rest is not None

    # Example path only; use your tenant's Workday REST API base URL + endpoint paths.
    payload = await api.rest.get_json("/your/rest/endpoint", correlation_id="job-002")
    print(payload)

asyncio.run(main())
```

Run it:

```bash
uv run python examples/rest_custom_object_definitions.py --environment sandbox
```

### Get a Bearer token (OAuth refresh-token flow)

If you want to debug an endpoint with `curl`, you can mint a short-lived access token from
an environment in `secrets.workday.json`:

```bash
uv run python examples/oauth_get_bearer_token.py --environment prod_rest
```

### SOAP example

```python
import asyncio
from workday_api import WorkdayApi

async def main() -> None:
    api = WorkdayApi.from_env_basic()
    assert api.soap is not None

    body_xml = """
    <wd:Get_Workers_Request xmlns:wd="urn:com.workday/bsvc">
      <wd:Response_Filter>
        <wd:Page>1</wd:Page>
        <wd:Count>1</wd:Count>
      </wd:Response_Filter>
    </wd:Get_Workers_Request>
    """.strip()

    xml = await api.soap.call(body_xml=body_xml, correlation_id="job-003")
    print(xml[:500])

asyncio.run(main())
```

See also:
- `examples/soap_get_historical_academic_records.py`
- `examples/soap_get_student_recruitments.py` (Student_Recruiting v46.0)
 
### Documentation

- **Getting started with Workday services** (REST, SOAP, RaaS, WSDL, testing): `docs/workday-overview.md`
- Custom Objects tenant setup: `docs/workday_rest_custom_objects_setup.md`

### Custom Objects (REST) example

- Example script: `examples/rest_custom_object_definitions.py`

### Secrets configuration (recommended)

For multi-environment settings, use the JSON secrets file pattern:

- Copy `secrets.workday.json.example` → `secrets.workday.json` (this is gitignored)
- Run examples with `--environment <name>` where `<name>` matches a top-level key in your `secrets.workday.json`
  (e.g. `sandbox`, `preview`, `prod`, `prod_rest`, etc.)

`--environment` overrides everything else. You can also override the secrets path with `--secrets-file`.

