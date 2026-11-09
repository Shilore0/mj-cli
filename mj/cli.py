"""命令行入口：敲 `mj` 回车，50/50 抽一个透明蜘蛛侠彩蛋放给你看。"""

from __future__ import annotations

import argparse
import os
import random
import sys
from pathlib import Path

from . import __version__, audio, manifest, term, window
from .paths import assets_dir

DESCRIPTION = """\
在终端里复刻抖音的「MJ」彩蛋：每次触发都独立掷一次硬币，
各 50% 的概率播放「倒挂」或「耍帅」的透明蜘蛛侠。

声音跟着大小写走：小写 mj 默认静音，加 --audio 才出声；
大写 MJ 一敲就带音乐（想安静就用 --no-audio）。
"""


def invoked_name() -> str:
    """用户实际敲的是哪个名字（mj 还是 MJ）。"""
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
  mj --window         # 用真正透明的桌面悬浮窗播放（需 PyGObject）
  mj --size 50        # 限制精灵宽度为 50 列
  mj --pick-only      # 只抽签不播放，方便验证概率
  mj --explain        # 打印这次抽到什么、有没有声音、用哪个素材
""",
    )
    parser.add_argument("effect", nargs="?", choices=["hang", "pose"],
                        help="指定彩蛋（默认随机，各 50%%）")
    parser.add_argument("--list", action="store_true", help="列出可用彩蛋后退出")
    parser.add_argument("--pick-only", action="store_true", help="只输出抽签结果，不播放")
    parser.add_argument("--explain", action="store_true",
                        help="不播放，打印这次抽到的彩蛋、声音开关和素材路径")
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
        effect = manifest.pick(items, forced=args.effect, rng=rng)
    except manifest.AssetError as error:
        print(error, file=sys.stderr)
        return 2

    with_sound, sound_reason = resolve_audio(args.audio, args.no_audio, invoked_name())

    if args.pick_only:
        print(f"{effect['id']}\t{effect.get('label', '')}")
        return 0

    if args.explain:
        wav = base / effect["wav"] if effect.get("wav") else None
        player = audio.find_player()
        print(f"effect : {effect['id']} ({effect.get('label', '')})")
        print(f"sound  : {'on' if with_sound else 'off'} —— {sound_reason}")
        print(f"audio  : {wav.name if wav else '无'} "
              f"({'存在' if wav and wav.exists() else '缺失'})")
        print(f"player : {os.path.basename(player[0]) if player else '未找到播放器（会静音）'}")
        print(f"frames : {effect['frames']}")
        print(f"assets : {base}")
        return 0

    fps = args.fps or float(effect.get("fps") or 30)

    if args.window:
        if window.play(effect, base, opacity=args.opacity, audio=with_sound):
            return 0
        print("透明窗口不可用（缺少 PyGObject/cairo 或没有合成器），改为在终端里播放。",
              file=sys.stderr)

    cached = effect.get("cache")
    if not cached:
        print("素材缺少终端帧包，请执行：python3 scripts/build_assets.py", file=sys.stderr)
        return 2

    if not sys.stdout.isatty() and not args.force:
        # 被重定向时不要往管道里塞几兆转义序列
        print(f"{effect.get('label', effect['id'])}")
        return 0

    entry, blob = manifest.load_terminal(base, effect["id"], args.theme)
    stage = term.TerminalStage(entry, blob, theme=args.theme)
    align = "top" if effect["id"] == "hang" else "center"
    sound = audio.Sound(base / effect["wav"], enabled=with_sound)
    try:
        with sound:
            stage.play(width=args.size, align=align, fps=fps)
    except BrokenPipeError:
        # 例如 `mj | head`：下游先关了管道，安静退出，别在收尾时再刷一段报错
        silence_stdout()
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
