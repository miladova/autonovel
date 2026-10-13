"""Tier-1 tests for the teaser VOICEOVER track (Phase 13).

A short coheres on a first-person VO spine; this synthesizes the shots'
`voiceover` lines into a narration track. `stub` = offline silent WAV ($0);
`edge` = free Microsoft Edge TTS (no key) via an injectable synth seam;
`elevenlabs` = paid via an injectable httpx client. No network in tests.
"""

from __future__ import annotations

import json
import subprocess
import sys
import wave
from pathlib import Path

from autonovel.teaser import vo
from autonovel.teaser.backends import RenderError
from autonovel.teaser.shots import Shot, Spine, Teaser


def _teaser() -> Teaser:
    return Teaser(title="What the Ledger Shows", length_s=58, provider="veo", mode="short",
                  spine=Spine(narrator="Jakob in old age"), shots=[
        Shot(id="01", role="hook", subject_name="J", subject_appearance="x",
             action="a", voiceover="Seventh son of a wool merchant."),
        Shot(id="02", role="escalation", subject_name="J", subject_appearance="x",
             action="b", voiceover="I learned the account books."),
        Shot(id="03", role="title", subject_name="J", subject_appearance="x",
             action="c", voiceover=""),  # the title beat holds — no VO
    ])


def test_narration_script_joins_lines_in_order_skipping_empty() -> None:
    # Joined with a space, not a newline — so neural TTS reads the spine as one
    # flowing monologue, not line-by-line clipped statements (Phase 13).
    s = vo.narration_script(_teaser())
    assert s == "Seventh son of a wool merchant. I learned the account books."


def test_estimate_duration_scales_with_words() -> None:
    short = vo.estimate_duration_s("one two three")
    long = vo.estimate_duration_s("one two three four five six seven eight nine ten")
    assert 0 < short < long


def test_stub_writes_silent_wav_sized_to_narration(tmp_path: Path) -> None:
    out = tmp_path / "vo.wav"
    p = vo.generate_vo("a b c d e f", out, provider="stub")
    assert p.exists()
    with wave.open(str(p), "rb") as w:
        assert w.getnframes() > 0  # a real, non-empty silent track


def test_edge_uses_injected_synth_no_key_no_network(tmp_path: Path) -> None:
    calls = {}

    def fake_synth(text, out_path, *, voice):  # noqa: ANN001
        calls["text"], calls["voice"] = text, voice
        Path(out_path).write_bytes(b"ID3edge-mp3")

    out = tmp_path / "vo.mp3"
    p = vo.generate_vo("hear this", out, provider="edge", voice="en-GB-RyanNeural",
                       synth=fake_synth)
    assert p.read_bytes() == b"ID3edge-mp3"
    assert calls["text"] == "hear this" and calls["voice"] == "en-GB-RyanNeural"
    assert not vo.needs_key("edge")          # free, no key
    assert vo.vo_key("edge") is None


def test_elevenlabs_uses_client_and_needs_key(tmp_path: Path) -> None:
    class Resp:
        status_code = 200
        content = b"\xff\xf3eleven-mp3"

    class Client:
        def __init__(self): self.posted = None

        def post(self, url, headers=None, json=None):  # noqa: A002
            self.posted = (url, headers, json)
            return Resp()

    c = Client()
    out = tmp_path / "vo.mp3"
    p = vo.generate_vo("spoken", out, provider="elevenlabs", token="k", voice="VOICEID", client=c)
    assert p.read_bytes() == b"\xff\xf3eleven-mp3"
    assert "VOICEID" in c.posted[0] and c.posted[1]["xi-api-key"] == "k"
    assert vo.needs_key("elevenlabs")


def test_elevenlabs_without_key_raises(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    for k in ("ELEVENLABS_API_KEY", "ELEVEN_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    try:
        vo.generate_vo("x", tmp_path / "v.mp3", provider="elevenlabs", client=object())
        assert False, "expected RenderError"
    except RenderError as e:
        assert e.kind == "auth"


def test_empty_text_raises(tmp_path: Path) -> None:
    try:
        vo.generate_vo("   ", tmp_path / "v.wav", provider="stub")
        assert False
    except RenderError as e:
        assert e.kind == "unsupported"


def test_cli_dry_run_reports_script_and_length(tmp_path: Path) -> None:
    t = tmp_path / "teaser.json"
    from autonovel.teaser import shots as _s
    _s.dump(_teaser(), t)
    out = subprocess.run([sys.executable, "-m", "autonovel.mechanical", "teaser-vo",
                          str(t), "--provider", "edge", "--dry-run", "--format", "json"],
                         capture_output=True, text=True)
    assert out.returncode == 0
    d = json.loads(out.stdout)
    assert d["provider"] == "edge" and d["needs_key"] is False
    assert d["lines"] == 2 and "wool merchant" in d["script"]


def test_cutlist_narration_round_trips_and_mixes(tmp_path: Path) -> None:
    from autonovel.teaser import assemble as asm
    ce = asm.CutEntry(shot_id="01", clip="a.mp4", duration_s=5.0, media="video")
    cl = asm.CutList(title="T", kind="video", entries=[ce],
                     narration_track="vo/narr.wav")
    assert asm.CutList.from_dict(cl.to_dict()).narration_track == "vo/narr.wav"
    cmd = " ".join(asm.ffmpeg_command(cl, tmp_path / "out.mp4"))
    assert "narr.wav" in cmd  # narration is an input
    # narration alone (no bed) → it's the audio map
    assert "-map" in cmd


def test_narration_ducks_a_music_bed_under_it(tmp_path: Path) -> None:
    from autonovel.teaser import assemble as asm
    ce = asm.CutEntry(shot_id="01", clip="a.png", duration_s=5.0)
    cl = asm.CutList(title="T", kind="image", entries=[ce],
                     audio_bed="music/bed.wav", narration_track="vo/narr.wav")
    cmd = " ".join(asm.ffmpeg_command(cl, tmp_path / "out.mp4"))
    assert "bed.wav" in cmd and "narr.wav" in cmd
    assert "sidechaincompress" in cmd  # the bed ducks UNDER the narration


def test_cli_stub_generates_offline(tmp_path: Path) -> None:
    t = tmp_path / "teaser.json"
    from autonovel.teaser import shots as _s
    _s.dump(_teaser(), t)
    out = subprocess.run([sys.executable, "-m", "autonovel.mechanical", "teaser-vo",
                          str(t), "--provider", "stub", "--format", "json"],
                         capture_output=True, text=True)
    assert out.returncode == 0
    d = json.loads(out.stdout)
    assert Path(d["out"]).exists() and Path(d["latest"]).exists()
