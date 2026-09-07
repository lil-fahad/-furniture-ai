import json
import logging
import signal
import threading

from furniture_ai.config import get_settings
from furniture_ai.db import make_engine, sessions
from furniture_ai.errors import DomainError, LeaseLost
from furniture_ai.jobs import checkpoint, claim, finish, heartbeat
from furniture_ai.pipeline import Pipeline
from furniture_ai.providers import Providers
from furniture_ai.storage import Storage

log = logging.getLogger("furniture.worker")


def execute(factory, settings, pipeline, job):
    stop, lost = threading.Event(), threading.Event()

    def renew():
        while not stop.wait(settings.lease_seconds / 3):
            try:
                if not heartbeat(factory, job.id, job.lease_token, settings):
                    lost.set()
                    return
            except Exception:
                # No commit is allowed without a valid lease, including after a DB outage.
                lost.set()
                return

    def save(stage, value):
        if lost.is_set():
            raise LeaseLost
        checkpoint(factory, job.id, job.lease_token, stage, value)

    thread = threading.Thread(target=renew, daemon=True)
    thread.start()
    try:
        result = pipeline.run(job, save)
        if lost.is_set():
            raise LeaseLost
        finish(factory, job, result=result, settings=settings)
        log.info(json.dumps({"job_id": job.id, "event": "succeeded"}))
    except LeaseLost:
        log.warning(json.dumps({"job_id": job.id, "event": "lease_lost"}))
    except Exception as error:
        safe = (
            error
            if isinstance(error, DomainError)
            else DomainError(
                "INTERNAL_ERROR", "Processing failed. Contact the administrator with this job ID.", 500, True
            )
        )
        log.error(
            json.dumps(
                {
                    "job_id": job.id,
                    "event": "failed",
                    "error_type": type(error).__name__,
                    "error_code": safe.code,
                }
            )
        )
        try:
            finish(factory, job, error=safe, settings=settings)
        except LeaseLost:
            pass
    finally:
        stop.set()
        thread.join(timeout=5)


def main():
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    settings = get_settings()
    engine = make_engine(settings.database_url)
    factory = sessions(engine)
    providers = Providers(settings)
    pipeline = Pipeline(settings, Storage(settings), providers)
    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    try:
        while not stop.is_set():
            try:
                job = claim(factory, settings)
                if job:
                    execute(factory, settings, pipeline, job)
                else:
                    stop.wait(1)
            except Exception as error:
                log.error(json.dumps({"event": "poll_failed", "error_type": type(error).__name__}))
                stop.wait(5)
    finally:
        providers.close()
        engine.dispose()


if __name__ == "__main__":
    main()
