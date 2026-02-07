CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE IF NOT EXISTS inbox_events (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source          VARCHAR(50) NOT NULL,
    source_channel  VARCHAR(100),
    source_user     VARCHAR(100),
    sender_user     VARCHAR(100),
    receiver_user   VARCHAR(100),
    thread_id       VARCHAR(200),
    text            TEXT NOT NULL,
    raw_json        JSONB,
    pipeline        VARCHAR(50),
    intake_tier     SMALLINT DEFAULT 2,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS tasks (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    todoist_id        VARCHAR(100),
    title             TEXT NOT NULL,
    task_type         VARCHAR(50),
    priority          INTEGER,
    assignee          VARCHAR(100),
    due_date          DATE,
    status            VARCHAR(30) DEFAULT 'open',
    escalation_state  VARCHAR(30) DEFAULT 'normal',
    enrichment_added  BOOLEAN DEFAULT false,
    sops_cited        JSONB,
    inbox_event_id    UUID REFERENCES inbox_events(id),
    created_at        TIMESTAMPTZ DEFAULT NOW(),
    updated_at        TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS enforcement_log (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id         UUID REFERENCES tasks(id),
    todoist_task_id VARCHAR(100),
    check_type      VARCHAR(30),
    has_update      BOOLEAN,
    notified_user   VARCHAR(100),
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS audit_log (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    actor           VARCHAR(100) NOT NULL,
    action          VARCHAR(100) NOT NULL,
    entity_type     VARCHAR(50),
    entity_id       UUID,
    details         JSONB,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS kb_docs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title           VARCHAR(255) NOT NULL,
    source_path     TEXT,
    content_text    TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS kb_chunks (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    doc_id          UUID REFERENCES kb_docs(id),
    chunk_index     INTEGER,
    chunk_text      TEXT NOT NULL,
    section_ref     VARCHAR(100),
    embedding       VECTOR(1536),
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS kb_chunks_embedding_idx ON kb_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 20);
CREATE INDEX IF NOT EXISTS audit_log_created_at_idx ON audit_log (created_at DESC);
CREATE INDEX IF NOT EXISTS tasks_escalation_state_due_date_idx ON tasks (escalation_state, due_date);
CREATE INDEX IF NOT EXISTS inbox_events_channel_created_at_idx ON inbox_events (source_channel, created_at DESC);
