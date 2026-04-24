"""Text-to-speech adapters.

Providers:
  - edge      : Microsoft Edge TTS via the open-source `edge-tts` package. 100% free, no key.
  - elevenlabs: premium quality, needs ELEVENLABS_API_KEY.
  - openai    : needs OPENAI_API_KEY.
  - none      : skip voiceover.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from tenacity import retry, stop_after_attempt, wait_exponential

from .config import env, load_config


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
def _elevenlabs_synthesize(text: str, out_path: Path) -> Path:
    from elevenlabs.client import ElevenLabs

    cfg = load_config().providers.tts
    api_key = env().elevenlabs_api_key
    if not api_key:
        raise RuntimeError("ELEVENLABS_API_KEY is not set")
    client = ElevenLabs(api_key=api_key)
    audio_stream = client.text_to_speech.convert(
        voice_id=cfg.voice_id,
        model_id=cfg.model,
        text=text,
        output_format="mp3_44100_128",
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "wb") as f:
        for chunk in audio_stream:
            if chunk:
                f.write(chunk)
    return out_path


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
def _openai_synthesize(text: str, out_path: Path) -> Path:
    from openai import OpenAI

    key = env().openai_api_key
    if not key:
        raise RuntimeError("OPENAI_API_KEY is not set")
    client = OpenAI(api_key=key)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with client.audio.speech.with_streaming_response.create(
        model="tts-1",
        voice="nova",
        input=text,
    ) as resp:
        resp.stream_to_file(str(out_path))
    return out_path


async def _edge_synth_async(text: str, voice: str, out_path: Path) -> None:
    import edge_tts

    communicate = edge_tts.Communicate(text=text, voice=voice, rate="-5%", pitch="-2Hz")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    await communicate.save(str(out_path))


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
def _edge_synthesize(text: str, out_path: Path) -> Path:
    cfg = load_config().providers.tts
    voice = cfg.voice_id or "en-US-AriaNeural"
    asyncio.run(_edge_synth_async(text, voice, out_path))
    return out_path


def synthesize(text: str, out_path: Path) -> Path | None:
    """Return path to voiceover mp3, or None if TTS disabled in config."""
    provider = load_config().providers.tts.provider
    if provider == "none":
        return None
    if provider == "edge":
        return _edge_synthesize(text, out_path)
    if provider == "elevenlabs":
        return _elevenlabs_synthesize(text, out_path)
    if provider == "openai":
        return _openai_synthesize(text, out_path)
    raise ValueError(f"Unknown TTS provider: {provider}")
