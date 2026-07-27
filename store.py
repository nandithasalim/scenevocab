import os
from typing import List, Dict, Optional
from urllib.parse import urlparse, urlunparse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

raw_url = os.environ["DATABASE_URL"]
raw_url = raw_url.replace("postgresql://", "postgresql+asyncpg://")

parsed = urlparse(raw_url)
DATABASE_URL = urlunparse(parsed._replace(query=""))
engine = create_async_engine(DATABASE_URL, connect_args={"ssl": "require"})
async_session = async_sessionmaker(engine, expire_on_commit=False)

async def init_db():
    async with engine.begin() as conn:
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS vocab_words (
                id SERIAL PRIMARY KEY,
                term TEXT NOT NULL,
                source_title TEXT,
                timestamp_sec REAL,
                line_said TEXT,
                prev_line TEXT,
                next_line TEXT,
                meaning TEXT,
                why_used TEXT,
                difficulty TEXT DEFAULT 'intermediate',
                added_at TIMESTAMPTZ DEFAULT now(),
                times_seen INT DEFAULT 0,
                times_correct INT DEFAULT 0,
                last_quizzed TIMESTAMPTZ,
                mastered BOOLEAN DEFAULT FALSE,
                UNIQUE (term, source_title)
            );
        """))


async def add_entries(entries: List[Dict]) -> int:
    added = 0
    async with async_session() as session:
        for e in entries:
            result = await session.execute(
                text("""
                    INSERT INTO vocab_words
                        (term, source_title, timestamp_sec, line_said, prev_line, next_line, meaning, why_used, difficulty)
                    VALUES (:term, :source_title, :timestamp_sec, :line_said, :prev_line, :next_line, :meaning, :why_used, :difficulty)
                    ON CONFLICT (term, source_title) DO NOTHING
                    RETURNING id
                """),
                {
                    "term": e["term"],
                    "source_title": e.get("source_title"),
                    "timestamp_sec": e.get("timestamp_sec"),
                    "line_said": e.get("line_said"),
                    "prev_line": e.get("prev_line"),
                    "next_line": e.get("next_line"),
                    "meaning": e.get("meaning"),
                    "why_used": e.get("why_used"),
                    "difficulty": e.get("difficulty", "intermediate"),
                }
            )
            if result.fetchone() is not None:
                added += 1
        await session.commit()
    return added


async def all_entries() -> List[Dict]:
    async with async_session() as session:
        result = await session.execute(
            text("SELECT * FROM vocab_words ORDER BY added_at DESC")
        )
        rows = result.mappings().all()
    return [dict(r) for r in rows]


async def due_for_review(limit: int = 15, difficulty: Optional[str] = None) -> List[Dict]:
    async with async_session() as session:
        if difficulty:
            result = await session.execute(
                text("""
                    SELECT * FROM vocab_words
                    WHERE mastered = FALSE AND difficulty = :difficulty
                    ORDER BY last_quizzed NULLS FIRST
                    LIMIT :limit
                """),
                {"difficulty": difficulty, "limit": limit}
            )
        else:
            result = await session.execute(
                text("""
                    SELECT * FROM vocab_words
                    WHERE mastered = FALSE
                    ORDER BY last_quizzed NULLS FIRST
                    LIMIT :limit
                """),
                {"limit": limit}
            )
        rows = result.mappings().all()
    return [dict(r) for r in rows]


async def record_quiz_result(term: str, source_title: str, correct: bool):
    async with async_session() as session:
        await session.execute(
            text("""
                UPDATE vocab_words
                SET times_seen = times_seen + 1,
                    times_correct = times_correct + :correct,
                    last_quizzed = now(),
                    mastered = (times_correct + :correct) >= 3
                WHERE lower(term) = lower(:term) AND source_title = :source_title
            """),
            {"correct": int(correct), "term": term, "source_title": source_title}
        )
        await session.commit()