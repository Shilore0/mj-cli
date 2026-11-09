"""音效播放：挑一个本机存在的播放器，后台放 wav，动画结束就收掉。

- Linux/macOS：pw-play / paplay / aplay / ffplay / mpv / sox / cvlc，谁在 PATH 就用谁。
- Windows：直接用标准库 winsound（异步播放 WAV，不需要装任何东西）。
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

# 按优先级排列：PipeWire / PulseAudio / ALSA / ffmpeg / mpv / sox
CANDIDATES = [
    ("pw-play", ["{file}"]),
    ("paplay", ["{file}"]),
    ("aplay", ["-q", "{file}"]),
    ("ffplay", ["-nodisp", "-autoexit", "-loglevel", "quiet", "-volume", "100", "{file}"]),
    ("mpv", ["--no-video", "--really-quiet", "--volume=100", "{file}"]),
    ("play", ["-q", "{file}"]),          # sox
    ("cvlc", ["--play-and-exit", "--quiet", "{file}"]),
]

WINSOUND = "winsound"


def _winsound():
    if sys.platform != "win32":
        return None
    try:
        import winsound
    except ImportError:
        return None
    return winsound


def find_player() -> tuple[str, list[str]] | None:
    """返回（播放器, 参数模板）。Windows 上返回 winsound 这个伪播放器。"""
    override = os.environ.get("MJ_AUDIO_CMD")
    if override:
        return override, []
    if _winsound() is not None:
        return WINSOUND, []
    for name, args in CANDIDATES:
        path = shutil.which(name)
        if path:
            return path, args
    return None


class Sound:
    """上下文管理器：进入时开播，退出时确保声音被收掉。"""

    def __init__(self, wav: Path | None, enabled: bool = True):
        self.wav = wav
        self.enabled = enabled
        self.proc: subprocess.Popen | None = None
        self.mode: str | None = None

    def __enter__(self) -> "Sound":
        if not self.enabled or not self.wav or not self.wav.exists():
            return self
        player = find_player()
        if not player:
            return self
        command, template = player

        if command == WINSOUND:
            winsound = _winsound()
            if winsound is None:
                return self
            try:
                winsound.PlaySound(
                    str(self.wav),
                    winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT,
                )
                self.mode = WINSOUND
            except (RuntimeError, OSError):
                self.mode = None
            return self

        args = [part.format(file=str(self.wav)) for part in template]
        if os.environ.get("MJ_AUDIO_CMD"):
            args = [str(self.wav)]
        try:
            self.proc = subprocess.Popen(
                [command, *args],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            self.mode = "process"
        except OSError:
            self.proc = None
        return self

    def __exit__(self, *exc_info) -> None:
        if self.mode == WINSOUND:
            winsound = _winsound()
            if winsound is not None:
                try:
                    winsound.PlaySound(None, winsound.SND_PURGE)
                except (RuntimeError, OSError):
                    pass
            self.mode = None
            return

        if not self.proc:
            return
        if self.proc.poll() is None:
            try:
                self.proc.terminate()
                self.proc.wait(timeout=1)
            except (OSError, subprocess.TimeoutExpired):
                try:
                    self.proc.kill()
                except OSError:
                    pass
