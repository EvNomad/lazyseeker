import logging
from fastapi import APIRouter, BackgroundTasks, Depends
from fastapi.responses import JSONResponse
from sqlmodel import Session

from backend.app.db import get_session
from backend.app.services.radar import run_crawl, get_crawl_log, _crawl_lock

router = APIRouter(prefix="/radar", tags=["radar"])
logger = logging.getLogger(__name__)


@router.post("/run")
async def trigger_crawl(background_tasks: BackgroundTasks, session: Session = Depends(get_session)):
    if _crawl_lock.locked():
        return JSONResponse(status_code=409, content={"detail": "Crawl already in progress"})
    background_tasks.add_task(_run_crawl_bg, session)
    return {"started": True}


def _run_crawl_bg(session: Session) -> None:
    import asyncio
    from backend.app.services.radar import run_crawl_async, _crawl_lock
    async def _run():
        async with _crawl_lock:
            await run_crawl_async(session)
    asyncio.run(_run())


@router.get("/log")
def get_log():
    entries = get_crawl_log()
    return [
        {
            "company_id": e.company_id,
            "company_name": e.company_name,
            "run_at": e.run_at,
            "status": e.status,
            "new_postings": e.new_postings,
            "error_message": e.error_message,
        }
        for e in entries
    ]
