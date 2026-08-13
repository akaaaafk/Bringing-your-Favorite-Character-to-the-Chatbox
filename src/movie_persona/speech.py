"""
Free neural TTS via Microsoft Edge Read Aloud voices (edge-tts).

No API key. Distinct voice per persona — not licensed actor likenesses.
"""
from __future__ import annotations

import io
from dataclasses import dataclass

import edge_tts


@dataclass(frozen=True)
class EdgeVoiceStyle:
    voice: str
    rate: str = "+0%"
    pitch: str = "+0Hz"
    volume: str = "+0%"


# Prefer voices labeled lively / expressive / passionate in Edge's catalog.
PERSONA_VOICES: dict[str, EdgeVoiceStyle] = {
    # Lively — fits neurotic, self-interrupting energy
    "alvy": EdgeVoiceStyle(
        "en-US-RogerNeural", rate="+6%", pitch="+10Hz", volume="+5%"
    ),
    # Passion / grit — still keep rate a touch slower for deadpan weight
    "jack": EdgeVoiceStyle(
        "en-US-GuyNeural", rate="-4%", pitch="-6Hz", volume="+0%"
    ),
    # Rational, controlled — clinical Bateman
    "bateman": EdgeVoiceStyle(
        "en-US-EricNeural", rate="+0%", pitch="-2Hz", volume="+0%"
    ),
    # Approachable, sincere — hesitant Ben
    "ben": EdgeVoiceStyle(
        "en-US-BrianNeural", rate="-2%", pitch="+4Hz", volume="+0%"
    ),
    # Cheerful / clear conversational — blunt Erin with more color
    "erin": EdgeVoiceStyle(
        "en-US-EmmaNeural", rate="+5%", pitch="+3Hz", volume="+8%"
    ),
}


def resolve_style(character: str) -> EdgeVoiceStyle:
    tag = character.strip().lower().replace(" ", "_")
    style = PERSONA_VOICES.get(tag)
    if style is None:
        raise ValueError(
            f"Unknown character '{character}'. Available: {sorted(PERSONA_VOICES)}"
        )
    return style


async def iter_mp3_chunks(text: str, character: str):
    """Yield MP3 bytes as edge-tts produces them (for streaming playback)."""
    clean = text.strip()
    if not clean:
        raise ValueError("text must be non-empty")
    if len(clean) > 4000:
        raise ValueError("text too long (max 4000 chars)")

    style = resolve_style(character)
    communicate = edge_tts.Communicate(
        clean,
        style.voice,
        rate=style.rate,
        pitch=style.pitch,
        volume=style.volume,
    )
    got = False
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            data = chunk["data"]
            if data:
                got = True
                yield data
    if not got:
        raise RuntimeError("edge-tts returned empty audio")


async def synthesize_mp3(text: str, character: str) -> bytes:
    """Return full MP3 bytes (non-streaming helper / fallback)."""
    buf = io.BytesIO()
    async for piece in iter_mp3_chunks(text, character):
        buf.write(piece)
    return buf.getvalue()
