from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List

from extract import Segment
from vocab_extract import extract_vocab
from store import add_entries, all_entries, init_db, get_weekly_quiz, record_quiz_result,get_new_words

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


class CaptionLine(BaseModel):
    text: str
    time: float


class TranscriptPayload(BaseModel):
    source_title: str
    segments: List[CaptionLine]

class QuizAnswer(BaseModel):
    term : str
    source_title : str
    correct : bool


@app.get("/health")
async def health():
    entries = await all_entries()
    return {"status": "ok", "word_count": len(entries)}

@app.get("/words")
async def get_words():
    entries = await all_entries()
    return {"words": entries}

@app.post("/transcript")
async def receive_transcript(payload: TranscriptPayload):
    if not payload.segments:
        return {"status": "empty", "added": 0}

    segments = [Segment(s.time, s.time, s.text) for s in payload.segments]

    print(f"[server] received {len(segments)} caption lines from '{payload.source_title}'")

    try:
        vocab_entries = await extract_vocab(segments, payload.source_title)
    except Exception as e:
        print(f"[server] LLM extraction failed: {e}")
        return {"status": "error", "error": str(e)}

    added = await add_entries(vocab_entries)
    return ({"status": "ok", "extracted": len(vocab_entries), "added": len(added), "new_words": added})

@app.get("/quiz")
async def get_weekly_quiz():
    words = await get_weekly_quiz(limit=10)
    return {"words": words}

@app.post("/quiz-result")
async def submit_quiz_result(result: QuizAnswer):
    await record_quiz_result(result.term, result.source_title, result.correct)
    return {"status": "ok"}

@app.get("/new-words")
async def new_words():
    words = await get_new_words()
    return {"words": words, "source_title": words[0]["source_title"] if words else None}