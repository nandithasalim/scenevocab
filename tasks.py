import os
from celery import Celery
from sqlalchemy import create_engine, text
from openai import OpenAI
import json
from dotenv import load_dotenv
load_dotenv()
celery_app = Celery("vocab_tasks", broker=os.environ["REDIS_URL"])

sync_engine = create_engine(
    os.environ["DATABASE_URL"],  # plain postgresql:// URL, NOT the +asyncpg version
    connect_args={"sslmode": "require"}
)

CHUNK_SIZE = 100

PROMPT_TEMPLATE = """You are helping a non-native English speaker build vocabulary from a movie/show transcript.

Below is a chunk of subtitle lines with timestamps (in seconds) and line numbers.

For this chunk, find words and phrases (including idioms, phrasal verbs, slang)
that would be genuinely useful new vocabulary for an English learner.
Skip common everyday words (the, go, happy, etc). Aim for ~3-8 items per chunk.

For each item return JSON with these fields:
- "term": the word or phrase
- "timestamp_sec": start time (seconds) where it's said
- "line_said": the exact subtitle line it appears in
- "prev_line": the subtitle line just before it (empty string if none)
- "next_line": the subtitle line just after it (empty string if none)
- "meaning": a clear, simple definition
- "why_used": one sentence on why this word/phrase fits the scene/tone
- "difficulty": one of "beginner", "intermediate", "advanced"

Return ONLY a JSON array, no other text.

TRANSCRIPT CHUNK:
{chunk_text}
"""


def _format_chunk(segments, start_idx):
    lines = []
    for i, seg in enumerate(segments):
        lines.append(f"[line {start_idx + i}] ({seg['time']:.1f}s) {seg['text']}")
    return "\n".join(lines)


def _call_llm_sync(prompt):
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    resp = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.choices[0].message.content


def _parse_json_array(text_):
    text_ = text_.strip()
    if text_.startswith("```"):
        text_ = text_.split("```")[1]
        if text_.startswith("json"):
            text_ = text_[4:]
    try:
        return json.loads(text_)
    except json.JSONDecodeError:
        start, end = text_.find("["), text_.rfind("]")
        return json.loads(text_[start:end + 1])


def _save_entries_sync(entries):
    added = 0
    with sync_engine.begin() as conn:
        for e in entries:
            result = conn.execute(
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
    return added


@celery_app.task
def process_transcript(source_title, segments):
    """
    segments is a plain list of dicts: [{"text": "...", "time": 1.2}, ...]
    This whole function runs in a separate Celery worker process, not inside
    the FastAPI request - so the user gets an instant response while this
    happens in the background.
    """
    all_entries = []
    for i in range(0, len(segments), CHUNK_SIZE):
        chunk = segments[i:i + CHUNK_SIZE]
        prompt = PROMPT_TEMPLATE.format(chunk_text=_format_chunk(chunk, i))
        raw = _call_llm_sync(prompt)
        try:
            entries = _parse_json_array(raw)
        except Exception as e:
            print(f"[celery] failed to parse chunk {i}: {e}")
            continue
        for e in entries:
            e["source_title"] = source_title
        all_entries.extend(entries)

    added = _save_entries_sync(all_entries)
    print(f"[celery] processed '{source_title}': {len(all_entries)} extracted, {added} added")
    return {"extracted": len(all_entries), "added": added}