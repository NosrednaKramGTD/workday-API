import asyncio
import os
import sys

from workday_api.auth import OAuthRefreshTokenBearerAuth
from workday_api.config import load_settings, parse_common_args


async def main() -> None:
    """
    Helper: mint a short-lived OAuth Bearer access token using the refresh-token flow.

    This loads credentials from `secrets.workday.json` (or another secrets file) based on
    `--environment`, then prints the access token to stdout.

    Example:
      uv run python examples/oauth_get_bearer_token.py --environment prod_rest | pbcopy

    Then:
      curl -i -H "Authorization: Bearer $(pbpaste)" "<workday-url>"
    """

    cfg = parse_common_args(sys.argv[1:])
    load_settings(
        environment=cfg.environment,
        secrets_file=cfg.secrets_file,
        extra_keys=["WORKDAY_REST_SCOPE"],
    )

    token_url = os.environ["WORKDAY_TOKEN_URL"]
    client_id = os.environ["WORKDAY_CLIENT_ID"]
    client_secret = os.environ["WORKDAY_CLIENT_SECRET"]
    refresh_token = os.environ["WORKDAY_REFRESH_TOKEN"]
    scope = os.environ.get("WORKDAY_REST_SCOPE")

    auth = OAuthRefreshTokenBearerAuth(
        token_url=token_url,
        client_id=client_id,
        client_secret=client_secret,
        refresh_token=refresh_token,
        scope=scope,
    )
    access_token = await auth.get_access_token()

    # Print token only; do not include extra text (so callers can pipe into other commands).
    print(access_token)


if __name__ == "__main__":
    asyncio.run(main())

