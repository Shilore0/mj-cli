"""终端播放：帧在构建时就渲染成了 ANSI 字符串，这里只负责解压和吐出去。

运行时不做任何像素运算，也不做颜色格式化——每帧只有一次 zlib 解压、一次
按行拆分、一次拼接光标定位，剩下的就是写 stdout。
"""

from __future__ import annotations

import shutil
import sys
import time
import zlib

ENTER_ALT = "\x1b[?1049h"
LEAVE_ALT = "\x1b[?1049l"
HIDE_CURSOR = "\x1b[?25l"
SHOW_CURSOR = "\x1b[?25h"
CLEAR = "\x1b[2J"
RESET = "\x1b[0m"


class TerminalStage:
    """按终端大小选一个预渲染尺寸，然后逐帧贴图。"""

    def __init__(self, entry: dict, blob: bytes, theme: str = "dark"):
        self.count = int(entry["count"])
        self.buckets = sorted(entry["buckets"], key=lambda b: b["width"])
        self.blob = blob
        self.theme = theme

    # ------------------------------------------------------------ 位置计算

    def choose(self, cols: int, rows: int, *, width: int | None = None,
               align: str = "center") -> dict:
        """挑一个放得下的桶：优先用户指定宽度，否则取放得下的最大一桶。

        一般不做裁剪——只有终端小到连最小一档都塞不下时才截断底部。
        """
        avail_rows = max(1, rows - 1)   # 留一行，免得触底滚动
        candidates = [b for b in self.buckets
                      if b["width"] <= cols and b["rows"] <= avail_rows]
        if not candidates:
            candidates = [self.buckets[0]]
        if width:
            capped = [b for b in candidates if b["width"] <= width]
            bucket = max(capped or candidates, key=lambda b: b["width"])
        else:
            bucket = max(candidates, key=lambda b: b["width"])

        clip = min(bucket["rows"], avail_rows)
        col = max(1, (cols - bucket["width"]) // 2 + 1)
        row = 1 if align == "top" else max(1, (avail_rows - clip) // 2 + 1)
        return {"bucket": bucket, "col": col, "row": row, "rows": clip}

    # ------------------------------------------------------------ 播放

    def play(self, *, width: int | None = None, align: str = "center",
             fps: float | None = None, out=None) -> None:
        out = out or sys.stdout
        fps = fps or 30.0
        try:
            cols, rows = shutil.get_terminal_size(fallback=(80, 24))
        except OSError:
            cols, rows = 80, 24
        cols, rows = max(20, cols), max(8, rows)

        spot = self.choose(cols, rows, width=width, align=align)
        bucket = spot["bucket"]
        prefixes = [f"\x1b[{spot['row'] + i};{spot['col']}H" for i in range(spot["rows"])]
        clip = spot["rows"]

        out.write(ENTER_ALT + CLEAR + HIDE_CURSOR)
        out.flush()
        interval = 1.0 / fps
        started = time.perf_counter()
        try:
            for index in range(self.count):
                delay = started + index * interval - time.perf_counter()
                if delay > 0.002:
                    time.sleep(delay)
                offset = bucket["offsets"][index]
                data = self.blob[offset:offset + bucket["lengths"][index]]
                lines = zlib.decompress(data).decode("utf-8").split("\n")
                if clip < len(lines):
                    lines = lines[:clip]
                out.write("".join([p + line for p, line in zip(prefixes, lines)]))
                out.flush()
        except KeyboardInterrupt:
            pass
        finally:
            # 管道可能已经被下游关掉（`mj | head`），收尾失败不该再抛异常
            try:
                out.write(RESET + SHOW_CURSOR + LEAVE_ALT)
                out.flush()
            except (BrokenPipeError, ValueError, OSError):
                pass
