from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List

from extract import Segment
from vocab_extract import extract_vocab
from store import add_entries, all_entries, init_db

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


@app.get("/health")
async def health():
    entries = await all_entries()
    return {"status": "ok", "word_count": len(entries)}


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
    print(f"[server] added {added} new vocab entries")
    return {"status": "ok", "extracted": len(vocab_entries), "added": added}