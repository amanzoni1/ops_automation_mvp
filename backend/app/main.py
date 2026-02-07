from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import settings
from app.logging_config import setup_logging
from app.routes import ask, enforce, health, inbound, debug


@asynccontextmanager
async def lifespan(_: FastAPI):
    setup_logging(settings.log_level)
    yield


app = FastAPI(title="Ops Automation MVP", lifespan=lifespan)

app.include_router(health.router)
app.include_router(inbound.router)
app.include_router(ask.router)
app.include_router(enforce.router)
app.include_router(debug.router)
