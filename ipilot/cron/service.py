import json
from datetime import datetime
from pathlib import Path

from croniter import croniter

from ipilot.cron.types import CronJob

class CronService:
    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.cron_dir = workspace / "cron"
        self.cron_dir.mkdir(parents=True, exist_ok=True)
        self.jobs_file = self.cron_dir / "jobs.json"
        self.jobs: dict[str, CronJob] = self._load()
    
    def _load(self) -> dict[str, CronJob]:
        if not self.jobs_file.exists():
            return {}
        data = json.loads(self.jobs_file.read_text(encoding="utf-8"))
        return {item["id"]: CronJob.from_dict(item) for item in data}

    def save(self) -> None:
        payload = [job.to_dict() for job in self.jobs.values()]
        self.jobs_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def add_job(self, job: CronJob) -> None:
        job.next_run_at = croniter(job.schedule, datetime.now()).get_next(datetime).isoformat()
        self.jobs[job.id] = job
        self.save()

    def due_jobs(self) -> list[CronJob]:
        now = datetime.now()
        ready: list[CronJob] = []
        for job in self.jobs.values():
            if not job.enabled or not job.next_run_at:
                continue
            if datetime.fromisoformat(job.next_run_at) <= now:
                ready.append(job)
        return ready

    def mark_job_run(self, job: CronJob) -> None:
        job.next_run_at = croniter(job.schedule, datetime.now()).get_next(datetime).isoformat()
        self.save()
