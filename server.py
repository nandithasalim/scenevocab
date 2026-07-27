from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
from dotenv import load_dotenv
load_dotenv()
from extract import Segment
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


from tasks import process_transcript

@app.post("/transcript")
async def receive_transcript(payload: TranscriptPayload):
    if not payload.segments:
        return {"status": "empty", "added": 0}

    segments = [s.dict() for s in payload.segments]
    process_transcript.delay(payload.source_title, segments)

    return {"status": "accepted", "message": "Processing in background"}