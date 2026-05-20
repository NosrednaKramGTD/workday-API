# Working with Workday services — overview

This is an introductory guide for developers building integrations against Workday. It explains why you often need **three different API styles** (REST, SOAP, and RaaS), where to find accurate contract documentation, and how to test calls before wiring them into code.

For repo-specific setup, see the [README](../README.md) and topic guides such as [Workday REST Custom Objects setup](workday_rest_custom_objects_setup.md).

## The short version

Most real Workday integrations are not “pick one API and go.” In practice you combine:

| Style | What it is | Typical use |
| --- | --- | --- |
| **RaaS** (Reports-as-a-Service) | Custom reports exposed as HTTP endpoints | Bulk reads, operational exports, fields not exposed elsewhere |
| **SOAP** (Workday Web Services / WWS) | XML operations grouped by functional service | Deep HCM, Student, Financials, and legacy integration patterns |
| **REST** | JSON APIs (tenant-hosted and WCP-hosted) | Newer product areas, Custom Objects, OAuth-first integrations |

Public documentation describes the *shape* of these APIs, but it is often incomplete for the exact tenant, version, and functional area you need. **Plan to pull WSDL and endpoint URLs from your instance** (or from the version-matched public directory) and validate requests in a non-production tenant before production rollout.

## Why you often need REST, SOAP, and RaaS together

Workday’s platform grew over many years. Different teams ship different integration surfaces, and coverage is uneven:

- **REST** is the preferred direction for new capabilities (including Workday Cloud Platform / WCP APIs such as Custom Object Definition). REST coverage is still not at parity with SOAP for many domains.
- **SOAP** remains the broadest programmatic surface. Hundreds of operations exist across services like `Human_Resources`, `Student_Recruiting`, `Integrations`, and `Financial_Management`. If REST does not expose what you need, SOAP usually does.
- **RaaS** fills gaps when neither REST nor SOAP gives you the right fields, joins, or business logic. Report writers can expose tenant-specific data as a stable URL without waiting for a new public operation.

A single integration flow often looks like this:

1. **RaaS** — nightly extract of workers, students, or ledger lines.
2. **SOAP** — submit a business process, fetch structured domain objects, or call an operation with no REST equivalent.
3. **REST** — read or write Custom Objects, call a WCP service, or use a modern JSON endpoint where it exists.

This repo’s `WorkdayApi` façade reflects that reality: RaaS is always available; REST and SOAP are optional depending on which base URLs and credentials you configure.

## Public documentation is a starting point, not the whole story

Workday publishes reference material on [community.workday.com](https://community.workday.com/), including:

- [SOAP API Reference](https://community-content.workday.com/en-us/public/products/platform-and-product-extensions/soap-api-reference.html) — entry point for Workday Web Services (WWS)
- [Public Web Services API Directory](https://community.workday.com/sites/default/files/file-hosting/productionapi/index.html) — SOAP services, operations, WSDL, and XSD by version
- [REST API Reference Directory](https://community.workday.com/sites/default/files/file-hosting/restapi/index.html) — REST services and OpenAPI-style listings

These directories are invaluable, but they have limits:

- **Version drift** — Production, Preview, and Sandbox tenants may run different WWS versions. A doc page for `v45.0` may not match your tenant’s active version.
- **Tenant-specific endpoints** — Hostnames and URL paths (`wd2-impl-services1`, `wd5-services1`, `api.us.wcp.workday.com`, etc.) vary by environment and region.
- **Security context** — An operation may be “public” in documentation but still return authorization errors until domain security policies and Integration System User (ISU) permissions are correct.
- **Incomplete examples** — Request/response samples in the public directory may not show every optional element your business process requires.

**Treat the public directory as an index.** For the service you are implementing, get the **WSDL (SOAP) or OpenAPI schema (REST) from the tenant or version directory you will actually call**, then build and test against that contract.

## SOAP: services, versions, and WSDL

Workday SOAP APIs are split into **functional services**, each with its own WSDL and version:

- `Human_Resources` — workers, organizations, personal data
- `Student_Recruiting`, `Student_Core`, `Academic_Foundation` — student lifecycle
- `Integrations` — integration system users, launch parameters
- Many others (Payroll, Benefits, Financial Management, …)

Each service is versioned (for example `v46.0`). Workday releases new WWS versions on a regular cadence and maintains backward compatibility **per version endpoint**, so pin the version you generate clients against.

### How to access WSDL from your Workday tenant

The most reliable way to get the **exact endpoint your tenant uses** is the **Public Web Services** report inside Workday:

1. Log into the target tenant (Sandbox or Preview is best for initial development).
2. Search for **Public Web Services** and open the report.
3. Find the service you need (for example **Human Resources** or **Student Recruiting**).
4. Open the row action menu (⋯) → **Web Service** → **View WSDL**.
   - The page can take a minute to load; the WSDL is large.
5. From the WSDL:
   - The **service URL** is what you POST SOAP envelopes to.
   - Set your client’s endpoint to that URL **without** the `?wsdl` query string.

You can also open the WSDL URL directly when you know the pattern:

```text
https://{cluster-host}/{ccx-path}/service/{tenant}/{Service_Name}/{version}?wsdl
```

Examples:

```text
https://wd2-impl-services1.workday.com/ccx/service/mytenant/Human_Resources/v46.0?wsdl
https://wd2-impl-services1.workday.com/ccx/service/mytenant/Student_Recruiting/v46.0?wsdl
```

At the bottom of the WSDL, look for `wsdl:service` / `soap:address` — the `location` attribute is your **SOAP endpoint**. Some newer or WCP-hosted SOAP entry points use a different host, for example:

```text
https://api.us.wcp.workday.com/soap/v46.0/Student_Recruiting
```

Those often expect **OAuth Bearer** tokens rather than WS-Security UsernameToken. Check the `WWW-Authenticate` response if you receive HTTP 401.

### Using the public WWS directory

When you do not have tenant access yet, use the [Public Web Services API Directory](https://community.workday.com/sites/default/files/file-hosting/productionapi/index.html):

1. Pick the **version** that matches your tenant (see **All Versions** or ask your Workday admin).
2. Open the **service** (for example [Human_Resources](https://community.workday.com/sites/default/files/file-hosting/productionapi/Human_Resources/v45.0/Human_Resources.html)).
3. Use the WSDL / XSD links on that page to download contracts for code generation or manual XML construction.
4. Use the [Operation Directory](https://community.workday.com/sites/default/files/file-hosting/productionapi/operations/index.html) to search for an operation name across services.

For Preview tenants, use the [Preview Public Web Services API Directory](https://community.workday.com/system/files/file-hosting/previewapi/index.html) instead — preview versions can change at service updates.

### SOAP testing checklist

- Create an **Integration System User** (ISU) and grant it an **Integration System Security Group** with domain permissions for the operations you call.
- Activate pending security policy changes before testing.
- For legacy tenant endpoints, authenticate with **WS-Security UsernameToken** (`username@tenantname` + password).
- For WCP SOAP endpoints, use an **OAuth access token** (`Authorization: Bearer …`).
- Start with a read-only `Get_*` operation and tight `Response_Filter` (page size 1) before larger payloads.

Repo examples:

- `examples/soap_get_historical_academic_records.py`
- `examples/soap_get_student_recruitments.py`

## REST: tenant APIs and WCP APIs

Workday REST appears in two common forms:

1. **Tenant-hosted REST** — URLs under your Workday hostname, often documented per service in the [REST Directory](https://community.workday.com/sites/default/files/file-hosting/restapi/index.html).
2. **WCP REST** — URLs such as `https://api.us.wcp.workday.com` for Custom Objects and other cloud platform APIs.

REST integrations usually require an **API Client** registered in the tenant (**Register API Client** task) and OAuth tokens (authorization code + refresh token, client credentials, or JWT bearer depending on your architecture).

Testing tips:

- Confirm `WORKDAY_REST_BASE_URL` and the token endpoint are **tenant-specific**; a wrong token URL commonly returns HTTP 404.
- Distinguish **401** (auth/token problem) from **403** (security group / scope problem).
- Use the service’s OpenAPI schema from the REST Directory where available; download it for offline reference the same way you would a WSDL.

Repo examples:

- `examples/rest_custom_object_definitions.py`
- `examples/oauth_get_bearer_token.py` — mint a short-lived bearer token for `curl` or Postman
- Setup guide: [workday_rest_custom_objects_setup.md](workday_rest_custom_objects_setup.md)

Some tenants also expose an **API Explorer** in the UI (search for **API Explorer** or browse documented REST paths for your tenant version). Use it to inspect resources and required scopes when available.

## RaaS: custom reports as HTTP APIs

RaaS exposes **Advanced Custom Reports** (or similar report types enabled for web services) at URLs like:

```text
https://{cluster-host}/ccx/service/customreport2/{tenant}/{ISU_or_owner}/{report_name}
```

Characteristics:

- Output formats typically include JSON, CSV, and XML (`fmt=json` etc.).
- Prompts become query parameters.
- Security is tied to the report owner / ISU and report sharing, not to WWS operation permissions.

RaaS is often the fastest path to a new extract, but reports are **tenant-configured artifacts** — there is no global public catalog equivalent to the WWS Operation Directory. You obtain report URLs from your Workday report developer or from the **Web Service** link on the report definition.

Repo example: `examples/raas_json.py` and the README quickstart.

## developer.workday.com and where testing actually happens

[developer.workday.com](https://developer.workday.com/) is Workday’s **developer and partner portal** — marketplace listings, Extend / app-building resources, and pointers into product documentation. It is the right place to orient yourself when building on the Workday platform, but **the detailed SOAP and REST contract directories live on community.workday.com** (links above).

For day-to-day integration testing, use this workflow:

1. **Non-production tenant** — Develop against Sandbox or Preview, not Production. Sandbox is typically refreshed from Production on a schedule; Preview exposes upcoming features earlier.
2. **ISU + API Client** — Create credentials purpose-built for integration (never a human user’s login).
3. **Public directories + tenant WSDL** — Cross-check operation names and XML shapes in the public directory, then confirm against the tenant WSDL before locking your client.
4. **Interactive HTTP tools** — Postman, Insomnia, or `curl` with a bearer token from `examples/oauth_get_bearer_token.py` are standard for REST. SOAP is usually easier to debug from a small script (see repo examples) because WS-Security headers are verbose in raw XML.
5. **This repo** — Use `--environment` with `secrets.workday.json` to swap Sandbox, Preview, and Production settings safely.

If you are working on **Workday Extend / WCP** apps, developer.workday.com documentation will point you at WCP-specific auth, scopes, and deployment flows — still plan on validating against your registered API client in a sandbox tenant.

## Choosing an API for a new requirement

Use this rough decision order:

1. **Is there a supported REST endpoint** in the REST Directory that matches the use case and your auth model? Prefer REST for new JSON-first integrations.
2. **If not, is there a SOAP operation** in the WWS directory? Search the Operation Directory, then pull the tenant WSDL for that service/version.
3. **If neither fits**, can a **custom report** expose the data or a Workday-calculated field? Use RaaS for read-heavy extracts.
4. **If you need writes or business processes**, SOAP or REST (where supported) is usually required — RaaS is predominantly read-only.

## Common pitfalls

| Symptom | Likely cause |
| --- | --- |
| HTTP redirect when POSTing SOAP | Endpoint URL is a UI or WSDL URL; drop `?wsdl` and use the `soap:address` location |
| SOAP Fault “Service unavailable” | Wrong service path (for example bare `.../bsvc` instead of `.../Student_Recruiting/v46.0`) |
| HTTP 401 with `WWW-Authenticate: Bearer` | WCP endpoint expects OAuth, not UsernameToken |
| HTTP 403 on REST | Missing domain security or OAuth scope for the API client’s ISU |
| Empty RaaS result | Report prompts, filters, or security differ from what you tested in the UI |
| Worked in Sandbox, fails in Prod | Different WWS version, stricter security, or report not deployed to Production |

## Related resources

- [SOAP API Reference (community)](https://community-content.workday.com/en-us/public/products/platform-and-product-extensions/soap-api-reference.html)
- [Public Web Services API Directory](https://community.workday.com/sites/default/files/file-hosting/productionapi/index.html)
- [REST API Reference Directory](https://community.workday.com/sites/default/files/file-hosting/restapi/index.html)
- [Workday Developers portal](https://developer.workday.com/)
- Repo: [README](../README.md), [Custom Objects setup](workday_rest_custom_objects_setup.md)
