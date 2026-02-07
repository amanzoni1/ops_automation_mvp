from pydantic import BaseModel


class AskRequest(BaseModel):
    query: str
    user_id: str | None = None
    source_channel: str | None = None
    thread_id: str | None = None


class Citation(BaseModel):
    source: str
    section: str | None = None
    chunk: str


class AskResponse(BaseModel):
    answer: str
    answer_title: str | None = None
    answer_bullets: list[str] = []
    answer_source: str | None = None
    citations: list[Citation]
    confidence: float
    tier: str
