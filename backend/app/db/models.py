from datetime import date, datetime
from typing import Any

from sqlalchemy import JSON, Boolean, Date, DateTime, ForeignKey, Integer, SmallInteger, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector


class Base(DeclarativeBase):
    pass


class InboxEvent(Base):
    __tablename__ = "inbox_events"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, server_default="gen_random_uuid()")
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    source_channel: Mapped[str | None] = mapped_column(String(100))
    source_user: Mapped[str | None] = mapped_column(String(100))
    sender_user: Mapped[str | None] = mapped_column(String(100))
    receiver_user: Mapped[str | None] = mapped_column(String(100))
    thread_id: Mapped[str | None] = mapped_column(String(200))
    text: Mapped[str] = mapped_column(Text, nullable=False)
    raw_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    pipeline: Mapped[str | None] = mapped_column(String(50))
    intake_tier: Mapped[int] = mapped_column(SmallInteger, default=2)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    tasks: Mapped[list["Task"]] = relationship(back_populates="inbox_event")


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, server_default="gen_random_uuid()")
    todoist_id: Mapped[str | None] = mapped_column(String(100))
    title: Mapped[str] = mapped_column(Text, nullable=False)
    task_type: Mapped[str | None] = mapped_column(String(50))
    priority: Mapped[int | None] = mapped_column(Integer)
    assignee: Mapped[str | None] = mapped_column(String(100))
    due_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(30), default="open")
    escalation_state: Mapped[str] = mapped_column(String(30), default="normal")
    enrichment_added: Mapped[bool] = mapped_column(Boolean, default=False)
    sops_cited: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    inbox_event_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("inbox_events.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    inbox_event: Mapped[InboxEvent | None] = relationship(back_populates="tasks")


class EnforcementLog(Base):
    __tablename__ = "enforcement_log"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, server_default="gen_random_uuid()")
    task_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("tasks.id"))
    todoist_task_id: Mapped[str | None] = mapped_column(String(100))
    check_type: Mapped[str | None] = mapped_column(String(30))
    has_update: Mapped[bool | None] = mapped_column(Boolean)
    notified_user: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, server_default="gen_random_uuid()")
    actor: Mapped[str] = mapped_column(String(100), nullable=False)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[str | None] = mapped_column(String(50))
    entity_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False))
    details: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class KbDoc(Base):
    __tablename__ = "kb_docs"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, server_default="gen_random_uuid()")
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    source_path: Mapped[str | None] = mapped_column(Text)
    content_text: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class KbChunk(Base):
    __tablename__ = "kb_chunks"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, server_default="gen_random_uuid()")
    doc_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("kb_docs.id"))
    chunk_index: Mapped[int | None] = mapped_column(Integer)
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    section_ref: Mapped[str | None] = mapped_column(String(100))
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1536))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
