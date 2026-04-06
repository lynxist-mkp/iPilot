import asyncio

from ipilot.cron.service import CronService


async def run_pending_jobs(service: CronService, bot) -> None:
    for job in service.due_jobs():
        await bot.run(
            job.prompt,
            session_key=f"cron:{job.id}",
            channel="cron",
            chat_id=job.id,
        )
        service.mark_job_run(job)


async def run_forever(service: CronService, bot, interval_seconds: int = 60):
    while True:
        await run_pending_jobs(service, bot)
        await asyncio.sleep(interval_seconds)

