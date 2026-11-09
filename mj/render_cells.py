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
def sampler(pack_w: int, pack_h: int, width: int, height: int) -> list[list[tuple[int, ...]]]:
    """每个目标像素对应一组源像素偏移（盒式采样，而不是最近邻）。

    最近邻会把细线整条丢掉——倒挂的蛛丝只有 1~2 像素宽，缩到 26 列就彻底消失。
    这里把每个目标像素覆盖的源像素都记下来，渲染时再做合并。
    """
    cols: list[tuple[int, int]] = []
    for x in range(width):
        x0 = min(pack_w - 1, x * pack_w // width)
        x1 = min(pack_w, max(x0 + 1, (x + 1) * pack_w // width))
        cols.append((x0 * 4, x1 * 4, 4))

    rows: list[list[tuple[int, ...]]] = []
    for py in range(height):
        y0 = min(pack_h - 1, py * pack_h // height)
        y1 = min(pack_h, max(y0 + 1, (py + 1) * pack_h // height))
        row: list[tuple[int, ...]] = []
        for start, stop, step in cols:
            offsets = []
            for sy in range(y0, y1):
                base = sy * pack_w * 4
                offsets.extend(range(base + start, base + stop, step))
            row.append(tuple(offsets))
        rows.append(row)
    return rows


def merge(data: bytes, offsets: tuple[int, ...]) -> tuple[int, int, int, int]:
    """把一盒源像素合成一个 (r, g, b, a)。

    普通区域按 alpha 加权平均（边缘更柔）；当盒里存在明显更亮的细线时直接取那颗，
    否则细线会被平均成近乎透明。alpha 用面积平均，保证覆盖度正确。
    """
    best = -1
    best_alpha = 0
    total_alpha = 0
    sum_r = sum_g = sum_b = 0

    for o in offsets:
        a = data[o + 3]
        if a:
            total_alpha += a
            sum_r += data[o] * a
            sum_g += data[o + 1] * a
            sum_b += data[o + 2] * a
            if a > best_alpha:
                best_alpha = a
                best = o

    if not best_alpha:
        return (0, 0, 0, 0)

    coverage = total_alpha // len(offsets)
    if best_alpha >= 64 and best_alpha > 3 * coverage // 2:
        # 细线（蛛丝、描边）：只占盒子里一小块，按面积平均会被稀释成灰色。
        # 这里保留最亮那颗的颜色，并把 alpha 提亮，让它在小档位上也看得见。
        return (data[best], data[best + 1], data[best + 2],
                min(255, best_alpha * 2))

    avg = (sum_r // total_alpha, sum_g // total_alpha, sum_b // total_alpha)

    # 中性灰白的亮部（蛛丝、高光）：盒子里还有黑描边/背景时，平均会把白线拉成灰线。
    # 只对低饱和度生效，人物身上的红/蓝不受影响。
    if max(avg) - min(avg) < 24 and coverage > 96:
        for o in offsets:
            a = data[o + 3]
            if a >= 128 and max(data[o], data[o + 1], data[o + 2]) - min(
                    data[o], data[o + 1], data[o + 2]) < 24:
                if max(data[o], data[o + 1], data[o + 2]) >= max(avg) + 40:
                    return (data[o], data[o + 1], data[o + 2], coverage)

    return (avg[0], avg[1], avg[2], coverage)


def _blend(r: int, g: int, b: int, a: int, base: int) -> tuple[int, int, int] | None:
    """把半透明像素混到主题底色上（深色主题混向黑，浅色混向白）。"""
    if not a:
        return None
    if a >= 255:
        return (r, g, b)
    return (
        (r * a + base * (255 - a)) // 255,
        (g * a + base * (255 - a)) // 255,
        (b * a + base * (255 - a)) // 255,
    )


def render_rows(data: bytes, plan: list[list[tuple[int, ...]]], width: int,
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
            tr, tg, tb, ta = merge(data, top[i])
            br, bgc, bb, ba = merge(data, bot[i])

            if not ta and not ba:
                blanks += 1
                continue

            if blanks:
                if cur_fg is not None or cur_bg is not None:
                    parts.append(RESET)
                    cur_fg = cur_bg = None
                parts.append(BLANK * blanks)
                blanks = 0

            if ta:
                char = UPPER
                fg = _blend(tr, tg, tb, ta, base)
                bg = _blend(br, bgc, bb, ba, base) if ba else None
            else:
                # 上像素透明、下像素有内容：改成下半块，只设前景色
                char = LOWER
                fg = _blend(br, bgc, bb, ba, base)
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
            # 行尾的空白格也必须先复位，否则会继承上一个像素的背景色，
            # 在画面上表现为一条横贯到行尾的色带（浅色像素 -> 白色横线）。
            if cur_fg is not None or cur_bg is not None:
                parts.append(RESET)
                cur_fg = cur_bg = None
            parts.append(BLANK * blanks)
        parts.append(RESET)
        lines.append("".join(parts))

    return lines
