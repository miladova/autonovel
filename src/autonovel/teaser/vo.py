"""Text-to-speech for the teaser VOICEOVER spine (Phase 13).

A `short` coheres on one first-person voiceover (teaser-craft §12). The VO
*text* is authored into `teaser.json` (`spine.narrator` + each shot's
`voiceover`); this module turns that text into an **audio narration track**
laid under the assembled cut (ducked beneath the score, like the music bed).

Same disciplines as ``music.py``/``backends.py``: an offline $0 stub, a
**free** real backend that needs no key, a paid upgrade, key resolution
(``--token`` → env → ``.env``), an injectable seam for tests, and a typed
``RenderError``. Providers:

  - **``stub``** — offline, zero-key, zero-network: a valid **silent** WAV
    sized to the narration's estimated duration, so generate→assemble can be
    rehearsed for $0.
  - **``edge``** — Microsoft Edge's free online TTS via the ``edge-tts``
    package: **no API key**, good neural voices. The easy "just start" path.
  - **``elevenlabs``** — ElevenLabs TTS (``ELEVENLABS_API_KEY``; reuses the
    same account as the audiobook pipeline) — paid, highest quality.

Python does HTTP + a silent-WAV writer + (optionally) drives ``edge-tts``;
no LLM, no quality judgement. The narration *writing* is the LLM's job.
"""

from __future__ import annotations

import os
import wave
from pathlib import Path
from typing import Any, Callable

from .backends import RenderError, resolve_key as _resolve_key

VO_ENV: dict[str, tuple[str, ...]] = {
    "elevenlabs": ("ELEVENLABS_API_KEY", "ELEVEN_API_KEY"),
}

VO_KEY_HELP: dict[str, str] = {
    "elevenlabs": "key at https://elevenlabs.io (ELEVENLABS_API_KEY) — same "
                  "account as the audiobook pipeline",
}

VO_PROVIDERS = ("stub", "edge", "elevenlabs")
_EXT = {"stub": "wav", "edge": "mp3", "elevenlabs": "mp3"}

# A sober, period-appropriate default narrator voice for `edge` (free). The
# command can override per teaser to match `spine.narrator` (e.g. an older
# male voice for Jakob looking back).
DEFAULT_EDGE_VOICE = "en-US-GuyNeural"
DEFAULT_ELEVEN_VOICE = "ErXwobaYiN019PkySvjV"  # "Antoni" (a default ElevenLabs voice id)

# Spoken-word pace for estimating narration duration (words/second). Trailer
# VO is delivered slowly and weightily, so ~2.3 wps, not conversational ~3.
_WORDS_PER_SECOND = 2.3


def vo_key(provider: str, *, token: str | None = None) -> str | None:
    """Resolve a VO backend key (token → env → .env). edge/stub need none."""
    if token:
        return token
    if provider in ("stub", "edge"):
        return None
    for name in VO_ENV.get(provider, ()):
        val = os.environ.get(name)
        if val:
            return val
    _resolve_key("__noop__")  # trigger the shared .env loader once
    for name in VO_ENV.get(provider, ()):
        val = os.environ.get(name)
        if val:
            return val
    return None


def needs_key(provider: str) -> bool:
    return provider == "elevenlabs"


def output_ext(provider: str) -> str:
    return _EXT.get(provider, "mp3")


def estimate_duration_s(text: str, *, words_per_second: float = _WORDS_PER_SECOND) -> float:
    """Estimate how long ``text`` takes to narrate (for the stub length + a
    pacing sanity-check against the cut runtime)."""
    words = len((text or "").split())
    return round(words / max(0.1, words_per_second), 2) if words else 0.0


def narration_script(teaser: Any) -> str:
    """Join a teaser's ordered shot ``voiceover`` lines into one narration
    script (the VO spine, in cut order). Skips empty lines (e.g. the title
    beat that holds).

    Lines are joined with a **space**, not a newline: a newline makes neural
    TTS (edge/elevenlabs) reset prosody and read each line as a clipped,
    terminal statement — the "bunch of short statements, not connected" sound.
    Joined as continuous prose, the voice carries intonation *across* the
    sentence boundaries and the spine plays as one monologue (which is the
    whole point of the VO — teaser-craft §12). The lines themselves still have
    to connect ("Connected, not a list"); this only stops the renderer from
    re-fragmenting authored prose that already flows."""
    lines = [s.voiceover.strip() for s in teaser.shots if s.voiceover.strip()]
    return " ".join(lines)


def _write_silent_wav(path: Path, seconds: float, *, rate: int = 44100) -> None:
    frames = max(1, int(rate * max(0.1, seconds)))
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\x00\x00" * frames)


def _edge_synth_default(text: str, out_path: Path, *, voice: str) -> None:  # pragma: no cover - needs package/network
    """Drive the free ``edge-tts`` package (no key). Imported lazily so the
    dependency is optional."""
    import asyncio
    import edge_tts

    async def _run() -> None:
        await edge_tts.Communicate(text, voice).save(str(out_path))

    asyncio.run(_run())


def _elevenlabs_bytes(text: str, *, key: str, voice: str, client: Any,
                      model: str | None) -> bytes:
    voice = voice or DEFAULT_ELEVEN_VOICE
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice}"
    headers = {"xi-api-key": key, "accept": "audio/mpeg"}
    payload: dict[str, Any] = {"text": text, "model_id": model or "eleven_multilingual_v2"}
    resp = client.post(url, headers=headers, json=payload)
    status = getattr(resp, "status_code", 200)
    if status in (401, 403):
        raise RenderError("elevenlabs: auth failed — check ELEVENLABS_API_KEY", kind="auth")
    if status == 402:
        raise RenderError("elevenlabs: payment required (quota)", kind="payment")
    if status >= 400:
        raise RenderError(f"elevenlabs: HTTP {status}", kind="http")
    return resp.content


def generate_vo(
    text: str,
    out_path: Path,
    *,
    provider: str = "stub",
    voice: str | None = None,
    token: str | None = None,
    model: str | None = None,
    client: Any = None,
    synth: Callable[..., None] | None = None,
) -> Path:
    """Synthesize a narration track from ``text`` to ``out_path``; return it.

    ``stub`` writes a silent WAV sized to the estimated narration length (no
    key, no network). ``edge`` drives the free ``edge-tts`` package (no key)
    via the injectable ``synth`` seam (default imports ``edge-tts``).
    ``elevenlabs`` POSTs via the injectable httpx-like ``client``. Raises
    ``RenderError`` (typed) on a missing key or an auth/payment/HTTP failure.
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    text = (text or "").strip()
    if not text:
        raise RenderError("vo: empty narration text (no voiceover lines)", kind="unsupported")

    if provider == "stub":
        _write_silent_wav(out_path, estimate_duration_s(text))
        return out_path

    if provider == "edge":
        v = voice or DEFAULT_EDGE_VOICE
        fn = synth or _edge_synth_default
        fn(text, out_path, voice=v)
        return out_path

    if provider == "elevenlabs":
        key = vo_key(provider, token=token)
        if not key:
            raise RenderError(
                f"{provider}: no API key — {VO_KEY_HELP.get(provider, 'set the key')}",
                kind="auth")
        if client is None:  # pragma: no cover - real network path
            import httpx
            client = httpx.Client(timeout=180, follow_redirects=True)
        data = _elevenlabs_bytes(text, key=key, voice=voice or DEFAULT_ELEVEN_VOICE,
                                 client=client, model=model)
        out_path.write_bytes(data)
        return out_path

    raise RenderError(f"unknown vo provider: {provider}", kind="unsupported")
