#!/usr/bin/env bash
# 卸载软链版（install.sh 装的）：只删 ~/.local/bin 下的 mj / MJ，不动仓库文件。
#
#   ./uninstall.sh            # 删软链
#   ./uninstall.sh --purge    # 删软链 + 删掉这一行 PATH 配置
set -uo pipefail

TARGET_DIR="${MJ_BIN_DIR:-$HOME/.local/bin}"
PURGE=0
[ "${1:-}" = "--purge" ] && PURGE=1

removed=0
for name in mj MJ; do
  if [ -L "$TARGET_DIR/$name" ] || [ -f "$TARGET_DIR/$name" ]; then
    rm -f "$TARGET_DIR/$name" && { echo "已移除 $TARGET_DIR/$name"; removed=1; }
  fi
done
[ "$removed" = 0 ] && echo "没有找到已安装的 mj / MJ（$TARGET_DIR）"

hash -r 2>/dev/null || true

if [ "$PURGE" = 1 ]; then
  for rc in "$HOME/.bashrc" "$HOME/.bash_profile" "$HOME/.zshrc"; do
    [ -f "$rc" ] || continue
    if grep -qs '\.local/bin' "$rc"; then
      cp "$rc" "$rc.mj-bak"
      grep -v '\.local/bin' "$rc.mj-bak" > "$rc"
      echo "已从 $rc 删掉含 .local/bin 的行（备份：$rc.mj-bak）"
    fi
  done
elif grep -qs '\.local/bin' "$HOME/.bashrc" 2>/dev/null; then
  echo
  echo "提示：~/.bashrc 里还有一行把 $TARGET_DIR 加进 PATH 的配置。"
  echo "     要一起清掉就重新执行：./uninstall.sh --purge"
fi

SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo
echo "仓库目录 $SELF_DIR 没有动；不需要的话可以 rm -rf 删掉。"
echo "装的是 deb / rpm 包的话，用：sudo dpkg -r mj-cli   或   sudo rpm -e mj-cli"
