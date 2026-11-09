"""素材清单与 50/50 抽签。"""

from __future__ import annotations

import json
import random
from pathlib import Path

from .paths import assets_dir


class AssetError(RuntimeError):
    pass


def load(base: Path | None = None) -> dict:
    base = base or assets_dir()
    path = base / "manifest.json"
    if not path.exists():
        raise AssetError(
            f"找不到素材清单：{path}\n"
            "请先在项目目录执行：python3 scripts/build_assets.py"
        )
    return json.loads(path.read_text("utf-8"))


def effects(data: dict) -> list[dict]:
    items = data.get("effects") or []
    if not items:
        raise AssetError("素材清单里没有任何彩蛋，请重新构建素材。")
    return items


def load_terminal(base: Path, effect_id: str, theme: str = "dark") -> tuple[dict, bytes]:
    """读取预渲染的 ANSI 帧包，返回（索引条目, 二进制块）。"""
    path = base / "terminal" / "index.json"
    if not path.exists():
        raise AssetError(f"找不到终端帧包索引：{path}")
    index = json.loads(path.read_text("utf-8"))
    if effect_id not in index:
        raise AssetError(f"帧包索引里没有 {effect_id}，请重新构建素材。")
    entry = index[effect_id]
    theme_entry = entry.get(theme) or entry["dark"]
    blob_path = base / theme_entry["file"]
    if not blob_path.exists():
        raise AssetError(f"找不到帧包文件：{blob_path}")
    return {"count": entry["count"], "buckets": theme_entry["buckets"]}, blob_path.read_bytes()


def pick(items: list[dict], forced: str | None = None,
         rng: random.Random | None = None) -> dict:
    """独立抽取一次：倒挂 / 耍帅 各 50%，不做「避免连击」的干预。"""
    if forced:
        for item in items:
            if item["id"] == forced or item.get("label") == forced:
                return item
        raise AssetError(f"未知的彩蛋：{forced}")
    if len(items) == 1:
        return items[0]
    rng = rng or random.SystemRandom()
    return items[0] if rng.random() < 0.5 else items[1]
