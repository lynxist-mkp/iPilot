$ErrorActionPreference = "Stop"

try {
    if (-not $env:STEPFUN_API_KEY) {
        throw "STEPFUN_API_KEY is not set. Run: `$env:STEPFUN_API_KEY = 'your-key'` in this PowerShell window first."
    }

    Write-Host ("STEPFUN_API_KEY is set ({0} chars)." -f $env:STEPFUN_API_KEY.Length)

    @'
import asyncio
import os
from ipilot.providers.openai_compat_provider import OpenAICompatibleProvider


async def main():
    provider = OpenAICompatibleProvider(
        api_key=os.environ["STEPFUN_API_KEY"],
        api_base="https://api.stepfun.com/v1",
        model="step-3.5-flash-2603",
    )
    response = await provider.chat(
        [{"role": "user", "content": "Reply with exactly: hello"}]
    )
    print(type(response).__name__)
    print(response.content)
    print(response.finish_reason)


asyncio.run(main())
'@ | uv run python -

    Start-Sleep -Seconds 10
}
catch {
    Write-Error $_
    Read-Host "Press Enter to close"
    exit 1
}
