#!/usr/bin/env bash
# 把 mj / MJ 装进 PATH。默认软链到 ~/.local/bin（改代码即时生效，不复制文件）。
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_DIR="${MJ_BIN_DIR:-$HOME/.local/bin}"

command -v python3 >/dev/null 2>&1 || { echo "需要 python3（>= 3.8）"; exit 1; }
python3 - <<'PY' || { echo "需要 Python 3.8 或更新版本"; exit 1; }
import sys
sys.exit(0 if sys.version_info >= (3, 8) else 1)
PY

chmod +x "$ROOT/bin/mj"
mkdir -p "$TARGET_DIR"

# 大小写各装一份：敲 mj 或者 MJ 都能触发（Linux 的文件名区分大小写）
for name in mj MJ; do
  ln -sf "$ROOT/bin/mj" "$TARGET_DIR/$name"
done

echo "已安装："
for name in mj MJ; do
  echo "  $TARGET_DIR/$name -> $ROOT/bin/mj"
done

case ":$PATH:" in
  *":$TARGET_DIR:"*) ;;
  *)
    echo
    echo "注意：$TARGET_DIR 不在 PATH 里，先把它加进去："
    echo "  echo 'export PATH=\"\$HOME/.local/bin:\$PATH\"' >> ~/.bashrc && source ~/.bashrc"
    ;;
esac

echo
echo "敲 mj（或 MJ）回车试试：各 50% 概率播「倒挂」或「耍帅」。"
