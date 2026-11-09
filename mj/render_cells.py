"""把 RGBA 帧转成 ANSI 行字符串（构建时使用）。

运行时不调用这里的代码——它只负责把构建好的字符串吐出去。抽出来单独放，
是为了让构建脚本和测试共用同一份渲染逻辑，避免两边各写一遍慢慢跑偏。

每个字符格子由上下两个像素拼成（▀ / ▄），透明像素直接留空格，让终端自己
的背景透出来。半透明边缘按主题色做一次混合：深色终端混向黑、浅色混向白。
"""

from __future__ import annotations

UPPER = "▀"   # 上半块：前景 = 上像素，背景 = 下像素
LOWER = "▄"   # 下半块：前景 = 下像素（上像素透明时用）
BLANK = " "
RESET = "\x1b[0m"


def sampler(pack_w: int, pack_h: int, width: int, height: int) -> list[list[int]]:
    """预计算每个目标像素对应的源字节偏移，避免逐帧做除法。"""
    colmap = [min(pack_w - 1, x * pack_w // width) * 4 for x in range(width)]
    rows: list[list[int]] = []
    for py in range(height):
        base = min(pack_h - 1, py * pack_h // height) * pack_w * 4
        rows.append([base + c for c in colmap])
    return rows


def render_rows(data: bytes, plan: list[list[int]], width: int,
                theme: str = "dark") -> list[str]:
    """按采样表把一帧渲染成 ANSI 行字符串列表（每行恰好 width 格）。"""
    base = 255 if theme == "light" else 0
    lines: list[str] = []
    memo: dict[tuple, str] = {}

    for r in range(len(plan) // 2):
        top = plan[2 * r]
        bot = plan[2 * r + 1]
        parts: list[str] = []
        cur_fg: tuple | None = None
        cur_bg: tuple | None = None
        blanks = 0

        for i in range(width):
            ot = top[i]
            ob = bot[i]
            ta = data[ot + 3]
            ba = data[ob + 3]

            if not ta and not ba:
                blanks += 1
                continue

            if blanks:
                if cur_fg is not None or cur_bg is not None:
                    parts.append(RESET)
                    cur_fg = cur_bg = None
                parts.append(BLANK * blanks)
                blanks = 0

            if ta == 255:
                fg = (data[ot], data[ot + 1], data[ot + 2])
            elif ta:
                fg = (
                    (data[ot] * ta + base * (255 - ta)) // 255,
                    (data[ot + 1] * ta + base * (255 - ta)) // 255,
                    (data[ot + 2] * ta + base * (255 - ta)) // 255,
                )
            else:
                fg = None

            if ta:
                char = UPPER
                if ba == 255:
                    bg = (data[ob], data[ob + 1], data[ob + 2])
                elif ba:
                    bg = (
                        (data[ob] * ba + base * (255 - ba)) // 255,
                        (data[ob + 1] * ba + base * (255 - ba)) // 255,
                        (data[ob + 2] * ba + base * (255 - ba)) // 255,
                    )
                else:
                    bg = None
            else:
                # 上像素透明、下像素有内容：改成下半块，只设前景色
                char = LOWER
                if ba == 255:
                    fg = (data[ob], data[ob + 1], data[ob + 2])
                else:
                    fg = (
                        (data[ob] * ba + base * (255 - ba)) // 255,
                        (data[ob + 1] * ba + base * (255 - ba)) // 255,
                        (data[ob + 2] * ba + base * (255 - ba)) // 255,
                    )
                bg = None

            if fg != cur_fg or bg != cur_bg:
                key = (fg, bg)
                sgr = memo.get(key)
                if sgr is None:
                    # 前景和背景一起写全，否则上一步残留的背景色会漏到透明格上
                    code = "38;2;%d;%d;%d" % fg if fg else "39"
                    code += ";48;2;%d;%d;%d" % bg if bg else ";49"
                    sgr = f"\x1b[{code}m"
                    memo[key] = sgr
                parts.append(sgr)
                cur_fg, cur_bg = fg, bg
            parts.append(char)

        if blanks:
            parts.append(BLANK * blanks)
        parts.append(RESET)
        lines.append("".join(parts))

    return lines
