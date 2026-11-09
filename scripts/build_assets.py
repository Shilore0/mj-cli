#!/usr/bin/env python3
"""从 Side-by-Side Alpha 源 MP4 构建 mj 命令行工具所需的全部素材。

源文件是「左半 = 亮度 Alpha 遮罩 / 右半 = RGB」的并排视频，放在 source/ 下：

    source/hang/output.mp4     倒挂
    source/pose/output.mp4     耍帅

（也兼容从原 MJ 扩展仓库直接跑的路径：蜘蛛侠-倒挂/3/output.mp4、
  蜘蛛侠-耍帅/2/output.mp4。）

本脚本产出（全部写入 assets/）：

    spiderman-<id>.webm   带 yuva420p 透明通道的 VP9，供窗口模式实时解码
    <id>.wav              48kHz / 16bit 立体声音轨
    terminal/<id>.bin     预渲染的 ANSI 帧包（zlib 压缩文本，含深/浅两套主题）
    terminal/index.json   帧包索引（每帧偏移、各尺寸档位）
    manifest.json         运行期读取的素材清单
    build-info.json       构建记录（裁剪框、档位宽度等）

用法：

    python3 scripts/build_assets.py            # 全部构建
    python3 scripts/build_assets.py --no-webm  # 跳过较慢的 webm 重编码
    FFMPEG_PATH=/usr/bin/ffmpeg python3 scripts/build_assets.py

依赖：ffmpeg（libvpx-vp9 支持透明通道）。ffprobe 可选，没有就用 ffmpeg 解析。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from mj import render_cells  # noqa: E402

ASSETS = ROOT / "assets"
TERMINAL_DIR = ASSETS / "terminal"

MASK_THRESHOLD = 2  # 遮罩亮度低于该值视为完全透明
PADDING = 24        # Alpha 联合包围盒外扩的安全边距
CACHE_WIDTH = 112   # 解码用的工作分辨率（之后按桶缩放到字符网格）
BUCKETS = [18, 26, 36, 50, 68]   # 预渲染的精灵宽度（字符列数）
THEMES = ["dark", "light"]       # 预渲染的背景主题

FPS = 30

SOURCE_CANDIDATES = {
    "hang": [ROOT / "source" / "hang" / "output.mp4",
             ROOT / "蜘蛛侠-倒挂" / "3" / "output.mp4"],
    "pose": [ROOT / "source" / "pose" / "output.mp4",
             ROOT / "蜘蛛侠-耍帅" / "2" / "output.mp4"],
}


def source_path(effect_id: str) -> Path:
    candidates = SOURCE_CANDIDATES[effect_id]
    for path in candidates:
        if path.exists():
            return path
    return candidates[0]


SOURCES = [
    {"id": "hang", "label": "倒挂", "input": source_path("hang")},
    {"id": "pose", "label": "耍帅", "input": source_path("pose")},
]


# ---------------------------------------------------------------- 基础工具


def log(message: str) -> None:
    print(message, flush=True)


def command_exists(name: str) -> bool:
    return shutil.which(name) is not None


def resolve_ffmpeg() -> str:
    env = os.environ.get("FFMPEG_PATH")
    if env and Path(env).exists():
        return env
    found = shutil.which("ffmpeg")
    if found:
        return found
    # 最后尝试 Python 包内置的静态 ffmpeg
    for python in ("python3", "python"):
        try:
            out = subprocess.run(
                [python, "-c", "import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())"],
                capture_output=True, text=True, timeout=30,
            )
            if out.returncode == 0 and out.stdout.strip():
                return out.stdout.strip()
        except Exception:
            pass
    raise SystemExit("找不到 ffmpeg。请安装 ffmpeg，或用 FFMPEG_PATH 指定路径。")


def resolve_ffprobe() -> str | None:
    env = os.environ.get("FFPROBE_PATH")
    if env and Path(env).exists():
        return env
    return shutil.which("ffprobe")


def run(args: list[str], *, capture: bool = True) -> subprocess.CompletedProcess:
    result = subprocess.run(
        args,
        cwd=ROOT,
        capture_output=capture,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        tail = (result.stderr or result.stdout or "").strip().splitlines()[-6:]
        raise SystemExit(f"命令失败：{' '.join(args[:3])} ...\n" + "\n".join(tail))
    return result


def probe_media(ffmpeg: str, ffprobe: str | None, path: Path) -> dict:
    if ffprobe:
        out = run([
            ffprobe, "-v", "error",
            "-show_entries", "stream=codec_type,codec_name,width,height,r_frame_rate:format=duration",
            "-of", "json", str(path),
        ]).stdout
        data = json.loads(out)
        video = next((s for s in data["streams"] if s["codec_type"] == "video"), None)
        if not video:
            raise SystemExit(f"{path} 没有视频流")
        return {
            "width": int(video["width"]),
            "height": int(video["height"]),
            "duration": float(data["format"]["duration"]),
            "has_audio": any(s["codec_type"] == "audio" for s in data["streams"]),
        }

    # 单纯 `ffmpeg -i <file>` 会以非零码退出，这里只关心它的 stderr
    probe = subprocess.run(
        [ffmpeg, "-hide_banner", "-i", str(path)],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    text = probe.stderr or ""
    size = re.search(r"Video:.*?\b(\d{2,5})x(\d{2,5})\b", text)
    duration = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", text)
    if not size or not duration:
        raise SystemExit(f"无法解析 {path} 的媒体信息")
    return {
        "width": int(size.group(1)),
        "height": int(size.group(2)),
        "duration": int(duration.group(1)) * 3600 + int(duration.group(2)) * 60 + float(duration.group(3)),
        "has_audio": "Audio:" in text,
    }


# ---------------------------------------------------------------- Alpha 分析


def alpha_union(ffmpeg: str, source: Path) -> dict:
    """扫描整段遮罩半区的联合包围盒（所有帧的并集）。"""
    result = subprocess.run(
        [
            ffmpeg, "-hide_banner", "-loglevel", "info", "-i", str(source), "-an",
            "-vf", f"crop=iw/2:ih:0:0,scale=in_range=tv:out_range=full,format=gray,"
                   f"bbox=min_val={MASK_THRESHOLD}",
            "-f", "null", os.devnull,
        ],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    boxes = [
        tuple(int(v) for v in m)
        for m in re.findall(r"x1:(\d+) x2:(\d+) y1:(\d+) y2:(\d+)", result.stderr or "")
    ]
    if not boxes:
        raise SystemExit(f"{source} 中找不到非透明帧")
    x1 = min(b[0] for b in boxes)
    x2 = max(b[1] for b in boxes)
    y1 = min(b[2] for b in boxes)
    y2 = max(b[3] for b in boxes)
    return {"x1": x1, "x2": x2, "y1": y1, "y2": y2}


def even_floor(value: float) -> int:
    return int(value // 2 * 2)


def even_ceil(value: float) -> int:
    return int(-(-value // 2) * 2)


def padded_crop(box: dict, half_width: int, height: int) -> dict:
    x = even_floor(max(0, box["x1"] - PADDING))
    y = even_floor(max(0, box["y1"] - PADDING))
    right = min(half_width, even_ceil(box["x2"] + 1 + PADDING))
    bottom = min(height, even_ceil(box["y2"] + 1 + PADDING))
    return {"x": x, "y": y, "width": right - x, "height": bottom - y}


def alpha_filter(crop: dict, half_width: int, tail: str) -> str:
    """左半取亮度作 alpha、右半取 RGB，合成 RGBA 后接 tail 处理链。"""
    return (
        "[0:v]split=2[masksrc][rgbsrc];"
        f"[masksrc]crop={crop['width']}:{crop['height']}:{crop['x']}:{crop['y']},"
        "scale=in_range=tv:out_range=full,format=gray[alpha];"
        f"[rgbsrc]crop={crop['width']}:{crop['height']}:{half_width + crop['x']}:{crop['y']}[color];"
        "[color][alpha]alphamerge,format=rgba,"
        "lut=a='if(lt(val,4),0,val)'"  # 阈值化，去掉遮罩里的微弱噪点
        f"{tail}"
    )


# ---------------------------------------------------------------- 构建步骤


def build_webm(ffmpeg: str, source: Path, crop: dict, half_width: int, output: Path) -> None:
    log(f"  · 编码透明 webm → {output.relative_to(ROOT)}（libvpx-vp9，稍慢）")
    run([
        ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-i", str(source),
        "-map_metadata", "-1", "-map_chapters", "-1",
        "-filter_complex", alpha_filter(crop, half_width, ",format=yuva420p[v]"),
        "-map", "[v]", "-map", "0:a?",
        "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p",
        "-b:v", "0", "-crf", "26", "-deadline", "good", "-cpu-used", "3",
        "-row-mt", "1", "-auto-alt-ref", "0",
        "-c:a", "libopus", "-b:a", "96k",
        "-metadata:s:v:0", "alpha_mode=1",
        str(output),
    ])


def audio_pcm_md5(ffmpeg: str, path: Path) -> str | None:
    """把音轨解码成统一格式再算摘要，用来确认 wav 确实来自这条源视频。"""
    result = subprocess.run(
        [ffmpeg, "-v", "error", "-i", str(path), "-vn",
         "-ac", "2", "-ar", "48000", "-f", "s16le", "-"],
        cwd=ROOT, capture_output=True,
    )
    if result.returncode != 0 or not result.stdout:
        return None
    return hashlib.md5(result.stdout).hexdigest()


def build_wav(ffmpeg: str, source: Path, output: Path, label: str) -> bool:
    """导出音轨，并校验它跟这条源片是同一段声音（防止换素材时错配）。"""
    expected = audio_pcm_md5(ffmpeg, source)
    if expected and output.exists() and output.stat().st_size > 1024:
        if audio_pcm_md5(ffmpeg, output) == expected:
            log(f"  · 音轨已存在且与「{label}」源片一致 → {output.relative_to(ROOT)}")
            return True
        log(f"  ! 已有音轨与「{label}」源片不符，重新导出")

    log(f"  · 提取音轨 → {output.relative_to(ROOT)}")
    result = subprocess.run(
        [
            ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-i", str(source),
            "-vn", "-ac", "2", "-ar", "48000", "-c:a", "pcm_s16le", str(output),
        ],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if result.returncode != 0:
        log("  ! 音轨提取失败，将只播放无声动画")
        return False

    actual = audio_pcm_md5(ffmpeg, output)
    if expected and actual != expected:
        raise SystemExit(
            f"音轨校验失败：{output.name} 与「{label}」源片不是同一段音频，"
            "请检查素材对应关系后再构建。"
        )
    log(f"  · 音轨校验通过（与「{label}」源片 PCM 一致）")
    return True


def build_ansi_pack(ffmpeg: str, source: Path, crop: dict, half_width: int,
                    output: Path) -> dict:
    """把每一帧提前渲染成 ANSI 字符串，运行时只解压 + 输出。

    每个桶（bucket）对应一种精灵宽度，命令行按终端大小挑最合适的一桶；
    因为字符串里只有颜色不依赖坐标，运行时只需要在每行前拼一个光标定位。
    """
    log(f"  · 预渲染 ANSI 帧 → {output.relative_to(ROOT)}"
        f"（桶宽 {'/'.join(str(b) for b in BUCKETS)} 列）")
    raw = subprocess.run(
        [
            ffmpeg, "-v", "error", "-i", str(source), "-an",
            "-filter_complex", alpha_filter(
                crop, half_width,
                ",premultiply=inplace=1,"
                f"scale={CACHE_WIDTH}:-2:flags=area,"
                "unpremultiply=inplace=1[v]",
            ),
            "-map", "[v]", "-pix_fmt", "rgba", "-f", "rawvideo", "-",
        ],
        cwd=ROOT, capture_output=True,
    )
    if raw.returncode != 0:
        raise SystemExit("终端帧解码失败：" + raw.stderr.decode("utf-8", "replace")[-400:])

    width = CACHE_WIDTH
    height = max(2, int(round(crop["height"] * CACHE_WIDTH / crop["width"] / 2)) * 2)
    frame_size = width * height * 4
    count = len(raw.stdout) // frame_size
    if count == 0:
        raise SystemExit("解码得到 0 帧，请检查素材")
    frames = [raw.stdout[i * frame_size:(i + 1) * frame_size] for i in range(count)]

    for theme in THEMES:
        plan_cache = {}
        blob = bytearray()
        buckets = []
        for bucket_w in BUCKETS:
            bucket_w = min(bucket_w, width)
            bucket_h = max(2, int(round(height * bucket_w / width / 2)) * 2)
            plan = plan_cache.get(bucket_w)
            if plan is None:
                plan = render_cells.sampler(width, height, bucket_w, bucket_h)
                plan_cache[bucket_w] = plan
            offsets: list[int] = []
            lengths: list[int] = []
            for frame in frames:
                text = "\n".join(render_cells.render_rows(frame, plan, bucket_w, theme))
                packed = zlib.compress(text.encode("utf-8"), 9)
                offsets.append(len(blob))
                lengths.append(len(packed))
                blob += packed
            buckets.append({
                "width": bucket_w,
                "height": bucket_h,
                "rows": bucket_h // 2,
                "offsets": offsets,
                "lengths": lengths,
            })

        suffix = "" if theme == "dark" else f".{theme}"
        path = output.with_name(f"{output.stem}{suffix}.bin")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(bytes(blob))
        yield theme, {
            "count": count,
            "file": f"terminal/{path.name}",
            "buckets": buckets,
            "bytes": len(blob),
        }


# ---------------------------------------------------------------- 主流程


def main() -> int:
    parser = argparse.ArgumentParser(description="构建 mj 的透明素材")
    parser.add_argument("--no-webm", action="store_true", help="跳过 webm 重编码（窗口模式需要它）")
    parser.add_argument("--no-terminal", action="store_true", help="跳过终端帧包")
    args = parser.parse_args()

    ffmpeg = resolve_ffmpeg()
    ffprobe = resolve_ffprobe()
    log(f"ffmpeg : {ffmpeg}")
    log(f"ffprobe: {ffprobe or '（不可用，改用 ffmpeg 解析）'}")

    TERMINAL_DIR.mkdir(parents=True, exist_ok=True)
    manifest_path = ASSETS / "manifest.json"
    previous = json.loads(manifest_path.read_text("utf-8")) if manifest_path.exists() else {}
    old_entries = {item["id"]: item for item in previous.get("effects", [])}
    manifest = {"cacheWidth": CACHE_WIDTH, "effects": []}
    build_info = {"maskThreshold": MASK_THRESHOLD, "padding": PADDING,
                  "cacheWidth": CACHE_WIDTH, "fps": FPS, "effects": []}

    for source in SOURCES:
        if not source["input"].exists():
            raise SystemExit(f"缺少源素材：{source['input']}")
        info = probe_media(ffmpeg, ffprobe, source["input"])
        half_width = info["width"] // 2
        if info["width"] % 2:
            raise SystemExit(f"并排素材宽度必须为偶数：{source['input']}")

        box = alpha_union(ffmpeg, source["input"])
        crop = padded_crop(box, half_width, info["height"])
        log(f"\n[{source['id']} / {source['label']}] {info['width']}x{info['height']}, "
            f"{info['duration']:.2f}s, 音频={'有' if info['has_audio'] else '无'}")
        log(f"  · Alpha 联合范围 x={box['x1']}..{box['x2']} y={box['y1']}..{box['y2']}")
        log(f"  · 裁剪 {crop['width']}x{crop['height']}+{crop['x']}+{crop['y']}（含 {PADDING}px 边距）")

        entry = dict(old_entries.get(source["id"], {}))
        entry.update({
            "id": source["id"],
            "label": source["label"],
            "fps": FPS,
            "duration": round(info["duration"], 3),
            "width": crop["width"],
            "height": crop["height"],
            "webm": f"spiderman-{source['id']}.webm",
            "wav": f"{source['id']}.wav",
            "frames": f"terminal/{source['id']}.bin",
        })

        if not args.no_webm:
            build_webm(ffmpeg, source["input"], crop, half_width,
                       ASSETS / entry["webm"])
        entry["audio"] = build_wav(ffmpeg, source["input"], ASSETS / entry["wav"],
                                   f"{source['id']} / {source['label']}")

        if not args.no_terminal:
            cache = {"count": 0, "themes": {}, "bytes": 0}
            index_path = TERMINAL_DIR / "index.json"
            index = json.loads(index_path.read_text("utf-8")) if index_path.exists() else {}
            for theme, pack in build_ansi_pack(ffmpeg, source["input"], crop, half_width,
                                               ASSETS / entry["frames"]):
                cache["count"] = pack["count"]
                cache["bytes"] += pack["bytes"]
                cache["themes"][theme] = {
                    "file": pack["file"],
                    "buckets": [
                        {k: b[k] for k in ("width", "height", "rows")} for b in pack["buckets"]
                    ],
                }
                index.setdefault(source["id"], {})[theme] = {
                    "file": pack["file"],
                    "count": pack["count"],
                    "buckets": pack["buckets"],
                }
            entry["cache"] = cache
            index.setdefault(source["id"], {})["count"] = cache["count"]
            index_path.write_text(json.dumps(index, ensure_ascii=False), "utf-8")
            biggest = cache["themes"]["dark"]["buckets"][-1]
            log(f"  · {cache['count']} 帧 × {len(BUCKETS)} 桶 × {len(THEMES)} 主题，"
                f"最大 {biggest['width']}x{biggest['rows']} 格，"
                f"共 {cache['bytes'] / 1024:.0f}KB")

        manifest["effects"].append(entry)
        build_info["effects"].append({"id": source["id"], **crop})

    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", "utf-8")
    (ASSETS / "build-info.json").write_text(
        json.dumps(build_info, ensure_ascii=False, indent=2) + "\n", "utf-8")
    log("\n素材构建完成。")


if __name__ == "__main__":
    sys.exit(main())
