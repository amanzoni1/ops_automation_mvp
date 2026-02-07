import asyncio
from pathlib import Path
from typing import Iterable

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import KbChunk, KbDoc
from app.db.session import AsyncSessionLocal
from app.services.knowledge_base import embed_texts

SOPS_DIR = Path(__file__).resolve().parents[1] / "data" / "sops"


def _chunk_words(words: list[str], size: int = 400, overlap: int = 50) -> Iterable[list[str]]:
    start = 0
    while start < len(words):
        end = min(start + size, len(words))
        yield words[start:end]
        start = max(end - overlap, end)


def _extract_sections(text: str) -> list[tuple[str | None, str]]:
    lines = text.splitlines()
    sections: list[tuple[str | None, str]] = []
    current_section: str | None = None
    buffer: list[str] = []

    def flush() -> None:
        if buffer:
            sections.append((current_section, "\n".join(buffer).strip()))

    for line in lines:
        if line.strip().startswith("§") or line.strip().startswith("##"):
            flush()
            current_section = line.strip()
            buffer = []
        else:
            buffer.append(line)
    flush()
    return sections


async def _reset_kb(session: AsyncSession) -> None:
    await session.execute(text("TRUNCATE kb_chunks CASCADE"))
    await session.execute(text("TRUNCATE kb_docs CASCADE"))
    await session.commit()


async def _ingest_doc(session: AsyncSession, path: Path) -> int:
    content = path.read_text(encoding="utf-8")
    doc = KbDoc(title=path.name, source_path=str(path), content_text=content)
    session.add(doc)
    await session.flush()

    sections = _extract_sections(content)
    chunks: list[tuple[str, str | None]] = []
    for section_ref, section_text in sections:
        words = section_text.split()
        for chunk_words in _chunk_words(words):
            chunk_text = " ".join(chunk_words)
            if section_ref:
                chunk_text = f"{section_ref}\n{chunk_text}"
            chunks.append((chunk_text, section_ref))

    embeddings = await embed_texts([chunk[0] for chunk in chunks])

    for idx, (chunk_text, section_ref) in enumerate(chunks):
        session.add(
            KbChunk(
                doc_id=doc.id,
                chunk_index=idx,
                chunk_text=chunk_text,
                section_ref=section_ref,
                embedding=embeddings[idx],
            )
        )

    await session.commit()
    return len(chunks)


async def ingest_all() -> None:
    paths = sorted(SOPS_DIR.glob("*.md"))
    total_chunks = 0
    async with AsyncSessionLocal() as session:
        await _reset_kb(session)
        for path in paths:
            total_chunks += await _ingest_doc(session, path)
    print(f"Ingested {len(paths)} docs, {total_chunks} chunks.")


def main() -> None:
    asyncio.run(ingest_all())


if __name__ == "__main__":
    main()
