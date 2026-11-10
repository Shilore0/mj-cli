"""命令行入口：敲 `mj` 回车，50/50 抽一个透明蜘蛛侠彩蛋放给你看。"""

from __future__ import annotations

import argparse
import os
import random
import re
import shutil
import sys
import unicodedata
from pathlib import Path

from . import __version__, audio, manifest, term, window
from .paths import PROJECT_ROOT, assets_dir

DESCRIPTION = """\
在终端里复刻抖音的「MJ」彩蛋：每次触发都独立掷一次硬币，
各 50% 的概率播放「倒挂」或「耍帅」的透明蜘蛛侠。

声音跟着大小写走：小写 mj 默认静音，加 --audio 才出声；
大写 MJ 一敲就带音乐（想安静就用 --no-audio）。
"""


def invoked_name() -> str:
    """用户实际敲的是哪个名字（mj 还是 MJ）。

    Windows 的 cmd / PowerShell 会把命令名规范化，`MJ` 到了 Python 这里就成了 `mj`，
    所以启动器会用 MJ_AS 环境变量把原始名字带过来。
    """
    override = os.environ.get("MJ_AS")
    if override:
        return override
    return os.path.basename(sys.argv[0] or "")


def audio_by_default(name: str) -> bool:
    """大写 MJ 调用 → 默认有音乐；小写 mj → 默认静音。

    只看程序名的大小写，不看参数。`python3 -m mj`、`bin/mj` 这类都是小写，
    想要声音就显式加 --audio。
    """
    stem = os.path.splitext(os.path.basename(name))[0]
    return stem == "MJ"


def resolve_audio(force_on: bool, force_off: bool, name: str) -> tuple[bool, str]:
    """返回（是否有声音, 给 --explain 看的理由）。"""
    if force_off:
        return False, "--no-audio"
    if force_on:
        return True, "--audio"
    if audio_by_default(name):
        return True, f"以大写 {os.path.basename(name)} 调用，默认带音乐"
    return False, f"以小写 {os.path.basename(name) or 'mj'} 调用，默认静音（加 --audio 出声）"


def _display_width(text: str) -> int:
    """中日韩字符占两格，按显示宽度算，才能对齐。"""
    return sum(2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1 for ch in text)


def print_where() -> None:
    """打印"这东西到底装在哪"，方便自己排查。"""
    launcher = os.path.abspath(sys.argv[0]) if sys.argv[0] else "(未知)"
    found = shutil.which("mj") or shutil.which("MJ")
    player = audio.find_player()
    rows = [
        ("版本", __version__),
        ("程序目录", str(PROJECT_ROOT)),
        ("启动器", launcher),
        ("素材", str(assets_dir())),
        ("Python", f"{sys.version.split()[0]}  {sys.executable}"),
        ("音频后端", os.path.basename(player[0]) if player else "无（会静音播放）"),
        ("PATH 里的 mj", found or "未找到（重开终端，或重跑安装脚本）"),
    ]
    width = max(_display_width(key) for key, _ in rows)
    for key, value in rows:
        pad = " " * (width - _display_width(key))
        print(f"{key}{pad} : {value}")


SEND_PATTERN = re.compile(r"^(?:mj)+$", re.IGNORECASE)


def parse_sends(words: list[str], repeat: int = 1) -> list[str | None]:
    """把命令行里的词展开成「一次发送」的列表（None 表示随机抽）。

    连发的语义跟抖音里一样——发几次就播几次：
      mj mjmjmj   -> [None, None, None]     写了 3 个 mj，播 3 次
      mj mj mj    -> [None, None, None]     分开写也算
      mj hang     -> ["hang"]
      mj mjmj --repeat 2 -> 4 次
    """
    sends: list[str | None] = []
    for word in words:
        lowered = word.lower()
        if lowered in ("hang", "pose"):
            sends.append(lowered)
        elif SEND_PATTERN.match(word):
            sends.extend([None] * (len(word) // 2))
        else:
            raise ValueError(word)

    if not sends:
        sends = [None]
    if repeat > 1:
        sends = sends * repeat
    return sends


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mj",
        description=DESCRIPTION,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
声音跟大小写走：
  mj                  # 静音（小写）
  MJ                  # 带音乐（大写）
  mj --audio          # 小写也出声

示例：
  mj                  # 抽一次，50% 倒挂 / 50% 耍帅
  mj hang             # 强制看倒挂
  mj pose             # 强制看耍帅
  mj mjmjmj           # 连发：写了 3 个 mj，就连续播 3 次
  mj mj mj            # 同上，分开写也算 3 次
  mj --repeat 3       # 也是连播 3 次
  mj --window         # 用真正透明的桌面悬浮窗播放（需 PyGObject）
  mj --size 50        # 限制精灵宽度为 50 列
  mj --pick-only      # 只抽签不播放，方便验证概率
  mj --explain        # 打印这次抽到什么、有没有声音、用哪个素材
""",
    )
    parser.add_argument("words", nargs="*", metavar="mj|hang|pose",
                        help="连发：每个 mj 算一次（mjmjmj = 3 次）；也可写 hang / pose 指定彩蛋")
    parser.add_argument("--repeat", "-n", type=int, default=1, metavar="N",
                        help="把整串再重复 N 遍（默认 1）")
    parser.add_argument("--list", action="store_true", help="列出可用彩蛋后退出")
    parser.add_argument("--pick-only", action="store_true", help="只输出抽签结果，不播放")
    parser.add_argument("--explain", action="store_true",
                        help="不播放，打印这次抽到的彩蛋、声音开关和素材路径")
    parser.add_argument("--where", action="store_true",
                        help="打印安装位置：程序目录、启动器、素材、Python、音频后端")
    parser.add_argument("--window", action="store_true",
                        help="用透明悬浮窗播放（失败自动退回终端）")
    parser.add_argument("--audio", "--sound", dest="audio", action="store_true",
                        help="强制播放音效（小写 mj 默认是静音的）")
    parser.add_argument("--no-audio", dest="no_audio", action="store_true",
                        help="强制静音（大写 MJ 默认带音乐）")
    parser.add_argument("--size", type=int, metavar="N",
                        help="限制精灵宽度（字符列数，档位 18/26/36/50/68）")
    parser.add_argument("--theme", choices=["dark", "light"], default="dark",
                        help="按哪种终端背景预渲染的版本，默认 dark")
    parser.add_argument("--fps", type=float, metavar="F", help="覆盖帧率，默认 30")
    parser.add_argument("--opacity", type=float, default=1.0,
                        help="窗口模式的整体不透明度（0-1）")
    parser.add_argument("--seed", type=int, help="固定随机种子，仅用于测试")
    parser.add_argument("--force", action="store_true",
                        help="输出不是终端时也强制渲染")
    parser.add_argument("--version", action="version", version=f"mj {__version__}")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.where:
        print_where()
        return 0

    base = assets_dir()

    try:
        data = manifest.load(base)
        items = manifest.effects(data)
    except manifest.AssetError as error:
        print(error, file=sys.stderr)
        return 2

    if args.list:
        print("可用彩蛋：")
        for item in items:
            cache = item.get("cache") or {}
            buckets = cache.get("themes", {}).get("dark", {}).get("buckets", [])
            sizes = "/".join(f"{b['width']}x{b['rows']}" for b in buckets) or "无帧包"
            print(f"  {item['id']:<5} {item.get('label', ''):<4} "
                  f"{item.get('duration', 0):.2f}s  {cache.get('count', 0)} 帧  "
                  f"音轨 {item.get('wav', '-'):<9} {sizes}")
        return 0

    rng = random.Random(args.seed) if args.seed is not None else None

    try:
        sends = parse_sends(args.words, args.repeat)
    except ValueError as bad:
        print(f"不认识「{bad.args[0]}」：位置参数只能写 mj 串（如 mjmjmj）、hang 或 pose。",
              file=sys.stderr)
        return 2

    with_sound, sound_reason = resolve_audio(args.audio, args.no_audio, invoked_name())

    if args.pick_only:
        # 连发时一行一次，脚本里好数
        for send in sends:
            effect = manifest.pick(items, forced=send, rng=rng)
            print(f"{effect['id']}\t{effect.get('label', '')}")
        return 0

    if args.explain:
        effect = manifest.pick(items, forced=sends[0], rng=rng)
        wav = base / effect["wav"] if effect.get("wav") else None
        player = audio.find_player()
        print(f"effect : {effect['id']} ({effect.get('label', '')})")
        print(f"sound  : {'on' if with_sound else 'off'} —— {sound_reason}")
        print(f"audio  : {wav.name if wav else '无'} "
              f"({'存在' if wav and wav.exists() else '缺失'})")
        print(f"player : {os.path.basename(player[0]) if player else '未找到播放器（会静音）'}")
        print(f"sends  : {len(sends)} 次连发")
        print(f"frames : {effect['frames']}")
        print(f"assets : {base}")
        return 0

    if not sys.stdout.isatty() and not args.force:
        # 被重定向时不要往管道里塞几兆转义序列，只报一下会播什么
        labels = []
        for send in sends:
            picked = manifest.pick(items, forced=send, rng=rng)
            labels.append(picked.get("label", picked["id"]))
        print("、".join(labels))
        return 0

    player = audio.find_player()
    loaded: dict[str, tuple] = {}
    use_window = args.window

    for send in sends:
        effect = manifest.pick(items, forced=send, rng=rng)
        fps = args.fps or float(effect.get("fps") or 30)

        if use_window:
            if window.play(effect, base, opacity=args.opacity, audio=with_sound):
                continue
            use_window = False          # 失败一次就够了，后面都走终端
            print("透明窗口不可用（缺少 PyGObject/cairo 或没有合成器），改为在终端里播放。",
                  file=sys.stderr)

        if not effect.get("cache"):
            print("素材缺少终端帧包，请执行：python3 scripts/build_assets.py", file=sys.stderr)
            return 2

        if effect["id"] not in loaded:
            loaded[effect["id"]] = manifest.load_terminal(base, effect["id"], args.theme)
        entry, blob = loaded[effect["id"]]
        stage = term.TerminalStage(entry, blob, theme=args.theme)
        align = "top" if effect["id"] == "hang" else "center"
        sound = audio.Sound(base / effect["wav"], enabled=with_sound)
        try:
            with sound:
                stage.play(width=args.size, align=align, fps=fps)
        except BrokenPipeError:
            # 例如 `mj | head`：下游先关了管道，安静退出，别在收尾时再刷一段报错
            silence_stdout()
            return 0
        except OSError:
            return 1
    return 0


def silence_stdout() -> None:
    try:
        devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull, sys.stdout.fileno())
    except OSError:
        pass


if __name__ == "__main__":
    raise SystemExit(main())
