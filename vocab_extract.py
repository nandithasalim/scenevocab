import asyncio
import json
import os
from typing import List, Dict
from extract import Segment

CHUNK_SIZE = 100
MAX_CONCURRENT_CALLS = 8

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

_semaphore = asyncio.Semaphore(MAX_CONCURRENT_CALLS)


def _format_chunk(segments: List[Segment], start_idx: int) -> str:
    lines = []
    for i, seg in enumerate(segments):
        lines.append(f"[line {start_idx + i}] ({seg.start:.1f}s) {seg.text}")
    return "\n".join(lines)


async def _call_llm(prompt: str) -> str:
    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])
    async with _semaphore:
        resp = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
        )
    return resp.choices[0].message.content


def _parse_json_array(text: str) -> List[Dict]:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("["), text.rfind("]")
        return json.loads(text[start:end + 1])


async def extract_vocab(segments: List[Segment], source_title: str) -> List[Dict]:
    chunks = [segments[i:i + CHUNK_SIZE] for i in range(0, len(segments), CHUNK_SIZE)]
    prompts = [
        PROMPT_TEMPLATE.format(chunk_text=_format_chunk(chunk, i * CHUNK_SIZE))
        for i, chunk in enumerate(chunks)
    ]

    raw_responses = await asyncio.gather(*[_call_llm(p) for p in prompts])

    all_entries = []
    for raw in raw_responses:
        try:
            entries = _parse_json_array(raw)
        except Exception as e:
            print(f"  [warn] failed to parse a chunk: {e}")
            continue
        for e in entries:
            e["source_title"] = source_title
        all_entries.extend(entries)
    return all_entries