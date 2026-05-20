# Workday REST Custom Objects (WCP) — tenant setup

This repo’s REST examples use **OAuth 2.0 refresh-token exchange** (no hardcoded access tokens).

The goal is to allow calls like:

- `GET /customObjectDefinition/v1/definitions`
- `GET /customObjectDefinition/v1/definitions/{id}`

…against a WCP REST host such as `https://api.us.wcp.workday.com`.

## What you need from Workday

### Create / register an API client

In your Workday tenant, you need an **API Client** capable of obtaining OAuth tokens and calling the
Custom Object Definition REST API.

At a high level:

- Create a new **API Client** intended for integrations (client id/secret).
- Record the tenant’s **Token Endpoint** URL (this is your `WORKDAY_TOKEN_URL`).
- Ensure the API client is configured for a flow that can mint a **refresh token** (your org’s policy
  may require auth-code + offline access / refresh token grant).

Important:

- The token endpoint is **tenant-specific**. If `WORKDAY_TOKEN_URL` is wrong you will often see
  **HTTP 404** when exchanging the refresh token.

### Obtain a refresh token

You must obtain a `refresh_token` for the API client (the process varies by tenant configuration and
Workday security policy).

General guidance:

- Use the supported Workday OAuth flow to mint a refresh token for the API client.
- Store **only** the refresh token + client credentials in your secrets manager and load them into
  your runtime environment; never paste access tokens into scripts.

### Security / authorization

You’ll need security that allows the API client’s principal (integration system user or equivalent)
to call the **Custom Object Definition** REST endpoints.

Minimum tenant prerequisites we’ve hit in practice:

- The **ISSG** (integration security group) needs **View** access to **Custom Object Management**.
- The **Integration API** configuration in the tenant must have the **scope system** enabled/available
  so the API client can be granted the required OAuth scopes for REST.

When troubleshooting:

- **401 Unauthorized**: OAuth problem (wrong token URL, wrong client credentials, expired/invalid refresh token)
- **403 Forbidden**: security problem (missing domain security policy / security group access / API permissions)

Workday security is tenant-specific; capture the final settings you apply in a local runbook.

## Repo configuration

### `.env` variables

Copy `.env.example` to `.env` and fill in values, then source it into your shell:

```bash
cp .env.example .env
```

The example scripts load configuration in this order:

- existing process env vars (highest precedence)
- JSON secrets file (`secrets.workday.json`) for the selected `--environment`
- `.env` via `python-dotenv` (lowest precedence)

Minimum vars for this REST example:

- `WORKDAY_REST_BASE_URL` (example: `https://api.us.wcp.workday.com`)
- `WORKDAY_TOKEN_URL`
- `WORKDAY_CLIENT_ID`
- `WORKDAY_CLIENT_SECRET`
- `WORKDAY_REFRESH_TOKEN`

Optional:

- `WORKDAY_CUSTOM_OBJECT_DEFINITION_ID` (to fetch a specific definition detail)

### Run the example

```bash
cp secrets.workday.json.example secrets.workday.json
uv run python examples/rest_custom_object_definitions.py --environment sandbox
```

If you prefer activating the venv for an interactive session:

```bash
source .venv/bin/activate
python examples/rest_custom_object_definitions.py --environment sandbox
```

## Operational best practices

- Treat `WORKDAY_CLIENT_SECRET` and `WORKDAY_REFRESH_TOKEN` like passwords.
- Rotate refresh tokens and client secrets per your org’s standard.
- Prefer running this code in an environment with a secrets manager; avoid long-lived credentials in local shells.
- Add correlation IDs (`X-Correlation-Id`) to help Workday/your team trace requests in logs.

