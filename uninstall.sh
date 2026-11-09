#!/usr/bin/env bash
# 卸载：只删软链，不动仓库里的任何文件。
set -euo pipefail

TARGET_DIR="${MJ_BIN_DIR:-$HOME/.local/bin}"
for name in mj MJ; do
  if [ -L "$TARGET_DIR/$name" ] || [ -f "$TARGET_DIR/$name" ]; then
    rm -f "$TARGET_DIR/$name"
    echo "已移除 $TARGET_DIR/$name"
  fi
done
