from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from ipilot.cron.service import CronService
from ipilot.cron.types import CronJob
from ipilot.heartbeat.service import run_pending_jobs


class RecordingBot:
    def __init__(self):
        self.calls: list[tuple[str, str, str, str]] = []

    async def run(self, message: str, session_key: str, channel: str | None = None, chat_id: str | None = None):
        self.calls.append((message, session_key, channel or "", chat_id or ""))
        return None


def test_cron_service_persists_and_recovers_jobs(tmp_path):
    service = CronService(tmp_path)
    job = CronJob(id="cron-demo", prompt="Reply with exactly: hello", schedule="*/5 * * * *")

    service.add_job(job)

    restored = CronService(tmp_path).jobs["cron-demo"]
    assert restored.id == "cron-demo"
    assert restored.prompt == "Reply with exactly: hello"
    assert restored.next_run_at is not None


@pytest.mark.asyncio
async def test_run_pending_jobs_executes_due_jobs_and_advances_schedule(tmp_path):
    service = CronService(tmp_path)
    job = CronJob(id="cron-demo", prompt="hello", schedule="*/5 * * * *")
    service.add_job(job)
    service.jobs["cron-demo"].next_run_at = (datetime.now() - timedelta(minutes=1)).isoformat()
    service.save()

    bot = RecordingBot()

    await run_pending_jobs(service, bot)

    assert bot.calls == [("hello", "cron:cron-demo", "cron", "cron-demo")]
    assert service.jobs["cron-demo"].next_run_at is not None
    assert datetime.fromisoformat(service.jobs["cron-demo"].next_run_at) > datetime.now() - timedelta(seconds=1)

