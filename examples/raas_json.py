import asyncio
import sys

from workday_api import WorkdayApi
from workday_api.config import load_settings, parse_common_args
 
 
async def main() -> None:
    cfg = parse_common_args(sys.argv[1:])
    load_settings(environment=cfg.environment, secrets_file=cfg.secrets_file)
    api = WorkdayApi.from_env_basic()
 
    data = await api.run_raas_json(
        report_url="WORKDAY_VIEW_URL_HERE",
        params={"Prompt_1": "value"},
        correlation_id="example-001",
    )

    print(data)
 
 
if __name__ == "__main__":
    asyncio.run(main())
