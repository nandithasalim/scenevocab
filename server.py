from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Optional

from extract import Segment
from vocab_extract import extract_vocab
from store import (
    init_db,
    add_entries,
    all_entries,
    get_new_words,
    get_weekly_quiz,
    record_quiz_result,
    due_for_review,
)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    await init_db()


@app.get("/health")
async def health():
    return {"status": "ok"}


class TranscriptSegment(BaseModel):
    text: str
    time: float


class TranscriptRequest(BaseModel):
    source_title: str
    segments: List[TranscriptSegment]
    user_id: str


@app.post("/transcript")
async def receive_transcript(payload: TranscriptRequest):
    if not payload.segments:
        return {"status": "empty", "added": 0}

    segments = [Segment(s.time, s.time, s.text) for s in payload.segments]

    try:
        vocab_entries = await extract_vocab(segments, payload.source_title)
    except Exception as e:
        return {"status": "error", "error": str(e)}

    added = await add_entries(vocab_entries, payload.user_id)
    return {"status": "ok", "extracted": len(vocab_entries), "added": len(added), "new_words": added}


@app.get("/words")
async def get_words(user_id: str):
    words = await all_entries(user_id)
    return {"words": words}


@app.get("/new-words")
async def new_words(user_id: str):
    words = await get_new_words(user_id)
    return {"words": words, "source_title": words[0]["source_title"] if words else None}


@app.get("/quiz")
async def get_quiz(user_id: str, limit: int = 10):
    words = await get_weekly_quiz(user_id, limit=limit)
    return {"words": words}


class QuizResult(BaseModel):
    term: str
    source_title: str
    correct: bool
    user_id: str


@app.post("/quiz-result")
async def submit_quiz_result(result: QuizResult):
    await record_quiz_result(result.term, result.source_title, result.correct, result.user_id)
    return {"status": "ok"}