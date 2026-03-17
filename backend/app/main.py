from contextlib import asynccontextmanager
from fastapi import FastAPI

import backend.app.models  # noqa: F401 — ensures all models are registered with SQLModel metadata
from backend.app.db import create_db_and_tables
from backend.app.routers.profile import router as profile_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    yield


app = FastAPI(lifespan=lifespan)

app.include_router(profile_router)


@app.get("/healthz")
def healthz():
    return {"status": "ok"}
