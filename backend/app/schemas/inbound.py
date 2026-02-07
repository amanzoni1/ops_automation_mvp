from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class Attachment(BaseModel):
    type: str
    name: str
    url: str


class InboundEvent(BaseModel):
    source: str
    source_channel: str | None = Field(default=None)
    source_user: str | None = Field(default=None)
    sender_user: str | None = Field(default=None)
    receiver_user: str | None = Field(default=None)
    thread_id: str | None = Field(default=None)
    text: str
    attachments: list[Attachment] = Field(default_factory=list)
    timestamp: datetime


class InboundResponse(BaseModel):
    status: str
    pipeline: str
    message: str
    details: dict[str, Any] | None = None
