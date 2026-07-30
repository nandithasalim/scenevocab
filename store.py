import os
from typing import List, Dict, Optional
from urllib.parse import urlparse, urlunparse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

raw_url = os.environ["DATABASE_URL"]
raw_url = raw_url.replace("postgresql://", "postgresql+asyncpg://")

parsed = urlparse(raw_url)
DATABASE_URL = urlunparse(parsed._replace(query=""))
engine = create_async_engine(
    DATABASE_URL,
    connect_args={"ssl": "require"},
    pool_pre_ping=True,
    pool_recycle=300,
)
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


async def add_entries(entries: List[Dict]) -> List[Dict]:
    added = []
    async with async_session() as session:
        for e in entries:
            result = await session.execute(
                text("""
                    INSERT INTO vocab_words (term, meaning, why_used, difficulty, source_title, timestamp_sec, example_sentence)
                    VALUES (:term, :meaning, :why_used, :difficulty, :source_title, :timestamp_sec, :example_sentence)
                    ON CONFLICT (term, source_title) DO NOTHING
                    RETURNING term, meaning, why_used, difficulty, source_title, example_sentence
                """),
                e,
            )
            row = result.first()
            if row:
                added.append(dict(row._mapping))
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

async def get_weekly_quiz(limit=10) -> List[Dict]:
    half = limit // 2
    async with async_session() as session:
        result = await session.execute(text(f"""
            (SELECT * FROM vocab_words ORDER BY wrong_count DESC LIMIT {half})
            UNION
            (SELECT * FROM vocab_words
             WHERE id NOT IN (SELECT id FROM vocab_words ORDER BY wrong_count DESC LIMIT {half})
             ORDER BY RANDOM() LIMIT {limit - half})
        """))
        return [dict(row._mapping) for row in result]


async def record_quiz_result(term: str, source_title: str, correct: bool):
    async with async_session() as session:
        if correct:
            await session.execute(
                text("UPDATE vocab_words SET wrong_count = 0 WHERE term = :term AND source_title = :source_title"),
                {"term": term, "source_title": source_title},
            )
        else:
            await session.execute(
                text("UPDATE vocab_words SET wrong_count = wrong_count + 1 WHERE term = :term AND source_title = :source_title"),
                {"term": term, "source_title": source_title},
            )
        await session.commit()

async def get_new_words() -> List[Dict]:
    async with async_session() as session:
        result = await session.execute(text("""
            SELECT * FROM vocab_words
            WHERE source_title = (
                SELECT source_title FROM vocab_words ORDER BY id DESC LIMIT 1
            )
            ORDER BY id DESC
        """))
        return [dict(row._mapping) for row in result]