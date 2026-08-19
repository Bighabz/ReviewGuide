"""
Cron Scheduler Service
Manages periodic background jobs
"""
from app.core.centralized_logger import get_logger
import asyncio
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.services.link_health_checker import run_health_check
from app.core.config import settings

logger = get_logger(__name__)


class SchedulerService:
    """
    Scheduler Service for managing background jobs

    Responsibilities:
    - Schedule periodic link health checks
    - Manage job lifecycle
    - Handle job errors and retries
    """

    def __init__(self):
        """Initialize scheduler"""
        self.scheduler = AsyncIOScheduler()
        self.is_running = False

    def start(self):
        """Start the scheduler and register jobs"""
        if self.is_running:
            logger.warning("Scheduler already running")
            return

        logger.info("=" * 80)
        logger.info("SCHEDULER SERVICE - Starting")

        try:
            # Check if link health checker is enabled
            if settings.ENABLE_LINK_HEALTH_CHECKER:
                # Schedule link health check job
                # Use configured interval
                interval_hours = settings.LINK_HEALTH_CHECK_INTERVAL_HOURS

                self.scheduler.add_job(
                    self._run_link_health_check,
                    trigger=IntervalTrigger(hours=interval_hours),
                    id="link_health_check",
                    name=f"Link Health Check (Every {interval_hours}h)",
                    replace_existing=True,
                    max_instances=1,  # Prevent overlapping runs
                )
                logger.info(f"Link health checker enabled (interval: {interval_hours}h)")
            else:
                logger.info("Link health checker disabled (ENABLE_LINK_HEALTH_CHECKER=false)")

            # KV sweeper (2026-08-18 Redis retirement): Postgres doesn't evict
            # expired kv rows on its own the way Redis did — reads filter on
            # expires_at for correctness; this job reclaims the disk.
            self.scheduler.add_job(
                self._run_kv_sweep,
                trigger=IntervalTrigger(minutes=15),
                id="kv_sweep",
                name="KV expired-row sweep (every 15m)",
                replace_existing=True,
                max_instances=1,
            )
            logger.info("KV expired-row sweeper scheduled (every 15m)")

            self.scheduler.start()
            self.is_running = True

            logger.info("Scheduler started successfully")

            jobs = self.scheduler.get_jobs()
            if jobs:
                logger.info("Scheduled jobs:")
                for job in jobs:
                    logger.info(f"  - {job.name} (ID: {job.id})")
                    logger.info(f"    Next run: {job.next_run_time}")
            else:
                logger.info("No jobs scheduled")

        except Exception as e:
            logger.error(f"Failed to start scheduler: {e}", exc_info=True)
            raise

    def stop(self):
        """Stop the scheduler"""
        if not self.is_running:
            logger.warning("Scheduler not running")
            return

        logger.info("Stopping scheduler...")
        self.scheduler.shutdown(wait=True)
        self.is_running = False
        logger.info("Scheduler stopped")

    async def _run_kv_sweep(self):
        """Background job: delete expired KV rows (pg_kv.sweep_expired)."""
        try:
            from app.core.pg_kv import sweep_expired
            await sweep_expired()
        except Exception as e:
            logger.error(f"KV sweep failed: {e}")

    async def _run_link_health_check(self):
        """
        Background job: Check link health
        Wrapped in try-catch to prevent scheduler from stopping on errors
        """
        job_start = datetime.utcnow()
        logger.info("=" * 80)
        logger.info(f"SCHEDULED JOB - Link Health Check started at {job_start}")

        try:
            stats = await run_health_check()

            if "error" in stats:
                logger.error(f"Link health check completed with errors: {stats['error']}")
            else:
                logger.info("Link health check completed successfully:")
                logger.info(f"  - Total: {stats.get('total', 0)}")
                logger.info(f"  - Healthy: {stats.get('healthy', 0)}")
                logger.info(f"  - Unhealthy: {stats.get('unhealthy', 0)}")
                logger.info(f"  - Updated: {stats.get('updated', 0)}")
                logger.info(f"  - Duration: {stats.get('duration_seconds', 0):.2f}s")

        except Exception as e:
            logger.error(f"Link health check job failed: {e}", exc_info=True)

        job_end = datetime.utcnow()
        duration = (job_end - job_start).total_seconds()
        logger.info(f"Link health check job finished in {duration:.2f}s")

    def get_job_status(self) -> dict:
        """Get status of all scheduled jobs"""
        if not self.is_running:
            return {"status": "stopped", "jobs": []}

        jobs = []
        for job in self.scheduler.get_jobs():
            jobs.append({
                "id": job.id,
                "name": job.name,
                "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
                "trigger": str(job.trigger),
            })

        return {
            "status": "running",
            "jobs": jobs,
        }

    async def run_job_now(self, job_id: str) -> dict:
        """
        Manually trigger a job to run now

        Args:
            job_id: Job identifier

        Returns:
            Result of job execution
        """
        if not self.is_running:
            return {"error": "Scheduler not running"}

        try:
            if job_id == "link_health_check":
                logger.info(f"Manually triggering job: {job_id}")
                await self._run_link_health_check()
                return {"status": "success", "message": f"Job {job_id} executed"}
            else:
                return {"error": f"Unknown job ID: {job_id}"}

        except Exception as e:
            logger.error(f"Error running job {job_id}: {e}", exc_info=True)
            return {"error": str(e)}


# Global scheduler instance
_scheduler: SchedulerService | None = None


def get_scheduler() -> SchedulerService:
    """Get or create global scheduler instance"""
    global _scheduler
    if _scheduler is None:
        _scheduler = SchedulerService()
    return _scheduler


def start_scheduler():
    """Start the global scheduler"""
    scheduler = get_scheduler()
    scheduler.start()


def stop_scheduler():
    """Stop the global scheduler"""
    scheduler = get_scheduler()
    scheduler.stop()


# Export
__all__ = ["SchedulerService", "get_scheduler", "start_scheduler", "stop_scheduler"]
