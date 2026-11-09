"""素材路径解析。"""

from __future__ import annotations

import os
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_DIR.parent


def assets_dir() -> Path:
    """返回素材目录。

    优先级：MJ_ASSETS 环境变量 → 项目根目录 assets/ → 包内 assets/。
    """
    override = os.environ.get("MJ_ASSETS")
    if override:
        return Path(override).expanduser().resolve()
    for candidate in (PROJECT_ROOT / "assets", PACKAGE_DIR / "assets"):
        if (candidate / "manifest.json").exists():
            return candidate
    return PROJECT_ROOT / "assets"
