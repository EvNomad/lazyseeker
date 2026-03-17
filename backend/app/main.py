from contextlib import asynccontextmanager
from fastapi import FastAPI
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlmodel import Session

import backend.app.models  # noqa: F401 — ensures all models are registered with SQLModel metadata
from backend.app.db import create_db_and_tables, engine
from backend.app.routers.profile import router as profile_router
from backend.app.routers.jobs import router as jobs_router
from backend.app.routers.radar import router as radar_router
from backend.app.routers.suggestions import router as suggestions_router


async def _scheduled_crawl():
    from backend.app.services.radar import run_crawl_async, _crawl_lock
    if _crawl_lock.locked():
        return
    async with _crawl_lock:
        with Session(engine) as session:
            await run_crawl_async(session)


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        _scheduled_crawl,
        "interval",
        hours=6,
        id="crawl_job",
    )
    scheduler.start()
    yield
    scheduler.shutdown()


app = FastAPI(lifespan=lifespan)

app.include_router(profile_router)
app.include_router(jobs_router)
app.include_router(radar_router)
app.include_router(suggestions_router)


@app.get("/healthz")
def healthz():
    return {"status": "ok"}
