"""桌面悬浮窗模式：把透明视频贴成一块真正的透明窗口。

需要 PyGObject（python3-gi + python3-gi-cairo）与一个带合成器的桌面
（GNOME / KDE / XFCE + compton 等）。没有这些条件时返回 False，
调用方会退回终端渲染。

说明：
- VP9 的 alpha 存在独立的 alpha 层，必须显式用 `-c:v libvpx-vp9` 解码，
  否则拿到的是不透明画面。
- 画面尺寸在启动时算好，ffmpeg 直接 pipe 出 BGRA 并做 alpha 预乘，
  Python 侧不需要逐像素处理。
"""

from __future__ import annotations

import shutil
import subprocess
import threading
from pathlib import Path

from .audio import Sound


def available() -> bool:
    if not shutil.which("ffmpeg"):
        return False
    try:
        import gi  # noqa: F401
        import cairo  # noqa: F401
    except Exception:
        return False
    return True


class _FramePipe:
    """后台线程把 ffmpeg 的 rawvideo 拉成一块块 BGRA 帧。"""

    def __init__(self, ffmpeg: str, path: Path, width: int, height: int):
        self.width = width
        self.height = height
        self.size = width * height * 4
        self.latest: bytearray | None = None
        self.finished = threading.Event()
        self.proc = subprocess.Popen(
            [
                ffmpeg, "-v", "error", "-c:v", "libvpx-vp9", "-i", str(path),
                "-vf",
                f"scale={width}:{height}:flags=lanczos,format=bgra,premultiply=inplace=1",
                "-pix_fmt", "bgra", "-f", "rawvideo", "-",
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _run(self) -> None:
        stream = self.proc.stdout
        try:
            while stream:
                chunk = stream.read(self.size)
                if not chunk or len(chunk) < self.size:
                    break
                self.latest = bytearray(chunk)
        finally:
            self.finished.set()
            try:
                self.proc.wait(timeout=2)
            except Exception:
                self.proc.kill()

    def close(self) -> None:
        if self.proc.poll() is None:
            try:
                self.proc.kill()
            except OSError:
                pass


def play(effect: dict, assets: Path, *, opacity: float = 1.0,
         audio: bool = True, hold: float = 0.6) -> bool:
    """播放透明悬浮窗动画。成功返回 True，环境不支持返回 False。"""
    if not available():
        return False

    import gi

    gi.require_version("Gtk", "3.0")
    gi.require_version("Gdk", "3.0")
    from gi.repository import Gdk, GLib, Gtk

    import cairo

    video = assets / effect["webm"]
    if not video.exists():
        return False

    ffmpeg = shutil.which("ffmpeg")
    display = Gdk.Display.get_default()
    if display is None:
        return False
    monitor = display.get_primary_monitor() or display.get_monitor(0)
    geometry = monitor.get_geometry()

    design_w = int(effect.get("width", 1080))
    design_h = int(effect.get("height", 1594))
    scale = min(geometry.height * 0.82 / design_h, geometry.width * 0.6 / design_w)
    width = max(2, int(design_w * scale) // 2 * 2)
    height = max(2, int(design_h * scale) // 2 * 2)

    pipe = _FramePipe(ffmpeg, video, width, height)

    window = Gtk.Window(type=Gtk.WindowType.POPUP)
    window.set_app_paintable(True)
    window.set_decorated(False)
    window.set_resizable(False)
    window.set_skip_taskbar_hint(True)
    window.set_skip_pager_hint(True)
    window.set_accept_focus(False)
    window.set_focus_on_map(False)
    window.set_opacity(opacity)

    visual = window.get_screen().get_rgba_visual()
    if visual is not None:
        window.set_visual(visual)

    try:
        window.set_type_hint(Gdk.WindowTypeHint.NOTIFICATION)
        window.set_keep_above(True)
    except Exception:
        pass

    if effect.get("id") == "hang":
        x = geometry.x + (geometry.width - width) // 2
        y = geometry.y
    else:
        x = geometry.x + (geometry.width - width) // 2
        y = geometry.y + (geometry.height - height) // 2
    window.move(max(geometry.x, x), max(geometry.y, y))
    window.set_size_request(width, height)

    state = {"surface": None, "buffer": None, "alive": True}

    def on_draw(_widget, cr):
        cr.set_operator(cairo.OPERATOR_SOURCE)
        cr.set_source_rgba(0, 0, 0, 0)
        cr.paint()
        cr.set_operator(cairo.OPERATOR_OVER)
        if state["surface"] is not None:
            cr.set_source_surface(state["surface"], 0, 0)
            cr.paint()
        return False

    window.connect("draw", on_draw)

    def make_click_through():
        """让鼠标事件穿透，别挡住用户桌面。"""
        try:
            gdk_window = window.get_window()
            if gdk_window is not None:
                gdk_window.input_shape_combine_region(cairo.Region(), 0, 0)
        except Exception:
            pass

    window.connect("realize", lambda _w: make_click_through())
    window.connect("screen-changed", lambda _w, _s: make_click_through())

    def tick():
        if not state["alive"]:
            return False
        if pipe.latest is not None:
            state["buffer"] = pipe.latest
            state["surface"] = cairo.ImageSurface.create_for_data(
                state["buffer"], cairo.FORMAT_ARGB32, width, height, width * 4
            )
            window.queue_draw()
        if pipe.finished.is_set() and pipe.latest is not None:
            GLib.timeout_add(int(hold * 1000), stop)
            return False
        return True

    def stop():
        state["alive"] = False
        pipe.close()
        Gtk.main_quit()
        return False

    window.show_all()
    GLib.timeout_add(16, tick)
    GLib.timeout_add(15000, stop)  # 兜底：任何情况下都不超过 15 秒

    sound = Sound(assets / effect["wav"], enabled=audio)
    with sound:
        Gtk.main()

    state["alive"] = False
    pipe.close()
    window.destroy()
    return True
