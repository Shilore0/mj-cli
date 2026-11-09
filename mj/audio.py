"""音效播放：挑一个本机存在的播放器，后台放 wav，动画结束就收掉。"""

from __future__ import annotations

import os
import shutil
import subprocess
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


def find_player() -> tuple[str, list[str]] | None:
    override = os.environ.get("MJ_AUDIO_CMD")
    if override:
        return override, []
    for name, args in CANDIDATES:
        path = shutil.which(name)
        if path:
            return path, args
    return None


class Sound:
    """上下文管理器：进入时开播，退出时确保子进程被回收。"""

    def __init__(self, wav: Path | None, enabled: bool = True):
        self.wav = wav
        self.enabled = enabled
        self.proc: subprocess.Popen | None = None

    def __enter__(self) -> "Sound":
        if not self.enabled or not self.wav or not self.wav.exists():
            return self
        player = find_player()
        if not player:
            return self
        command, template = player
        args = [part.format(file=str(self.wav)) for part in template]
        if os.environ.get("MJ_AUDIO_CMD"):
            command = os.environ["MJ_AUDIO_CMD"]
            args = [str(self.wav)]
        try:
            self.proc = subprocess.Popen(
                [command, *args],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        except OSError:
            self.proc = None
        return self

    def __exit__(self, *exc_info) -> None:
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
