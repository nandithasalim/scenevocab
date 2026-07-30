import asyncio
import json
import os
from typing import List, Dict
from extract import Segment

CHUNK_SIZE = 100
MAX_CONCURRENT_CALLS = 8

PROMPT_TEMPLATE = """You are helping a non-native English speaker build vocabulary from a movie/show transcript.

Below is a chunk of subtitle lines with timestamps (in seconds) and line numbers.

Find words and phrases (idioms, phrasal verbs, slang, less common single words) that are genuinely NEW and USEFUL vocabulary for an English learner. Be strict — most subtitle lines contain zero worthwhile words. Aim for 2-5 items per chunk, not every line.

SKIP entirely — never include these, even as "beginner":
happy, sad, tired, busy, angry, curious, valuable, robbed, help, walk, talk, see, want,
go, get, come, look, nice, good, bad, big, small, fast, slow, easy, hard, work, home,
friend, family, time, day, night, love, like, thing, way, feel, know, think, tell, ask,
give, take, make, find, use, need, try, call
Also skip simple phrasal verbs a learner already knows: go on, get up, sit down, come in, look at, wait for.
Also skip common idioms most learners already know: read between the lines, ulterior motive,
piece of cake, break the ice, hit the road, once in a blue moon.

If a word or phrase is common enough that an intermediate ESL learner already knows it, SKIP IT.
"Beginner" does NOT mean "common" — it means a genuinely useful word that's simply easier
than an intermediate/advanced pick. Follow this calibration closely:

- beginner: reluctant, irritated, postpone, overwhelmed, backfire, hold a grudge
- intermediate : condescending, elusive, insinuate, meticulous, ambivalent, pragmatic
- advanced: vicissitude, perspicacious, obsequious, ephemeral, obfuscate, insidious

For each item return JSON with:
- "term": the word or phrase
- "timestamp_sec": start time (seconds)
- "example_sentence": the EXACT subtitle line it appears in, verbatim
- "prev_line": subtitle line just before (empty string if none)
- "next_line": subtitle line just after (empty string if none)
- "meaning": a clear, simple definition
- "why_used": one sentence on why this word/phrase fits the scene/tone
- "difficulty": "beginner", "intermediate", or "advanced" — follow the calibration above strictly

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