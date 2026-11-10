#!/usr/bin/env bash
# 从 GitHub 拉最新代码并刷新安装（源码安装用）。
#
#   ./update.sh            # 有更新就拉下来，并重跑 install.sh
#   ./update.sh --check    # 只检查有没有新版本，不动任何文件
#   ./update.sh --force    # 本地改过代码也照样更新（丢弃本地改动）
#
# 装的是 deb / rpm 的话不要用这个，直接装新包（sudo dpkg -i / sudo rpm -Uvh）。

set -uo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_DIR" || exit 1

BRANCH="${MJ_UPDATE_BRANCH:-main}"
REMOTE="${MJ_UPDATE_REMOTE:-origin}"
CHECK_ONLY=0
FORCE=0

usage() {
  cat <<'EOF'
用法：./update.sh [选项]

  (无参数)     拉取最新代码，然后重跑 install.sh 刷新软链
  --check      只检查有没有新版本，不改任何文件
  --force      本地有改动也照样更新（丢弃对已跟踪文件的修改）
  -h, --help   显示这段说明

环境变量：
  MJ_UPDATE_REMOTE   远程名，默认 origin
  MJ_UPDATE_BRANCH   分支名，默认 main
EOF
}

for arg in "$@"; do
  case "$arg" in
    --check) CHECK_ONLY=1 ;;
    --force) FORCE=1 ;;
    -h|--help) usage; exit 0 ;;
    *) printf '未知参数：%s\n\n' "$arg"; usage; exit 2 ;;
  esac
done

current_version() {
  sed -n 's/^__version__ = "\(.*\)"/\1/p' mj/__init__.py 2>/dev/null
}

# ---------------------------------------------------------------- 前置检查

if ! command -v git >/dev/null 2>&1; then
  echo "找不到 git，装一下再试（Debian/Ubuntu：sudo apt install git）。" >&2
  exit 2
fi

if [ ! -d .git ]; then
  cat >&2 <<'EOF'
这个目录不是 git 仓库，没法自动更新。
如果你是下载 zip 解压的：重新下载最新版本覆盖即可（先备份自己的改动），
或者改用 clone：git clone https://github.com/Shilore0/mj-cli.git
EOF
  exit 2
fi

if ! git remote get-url "$REMOTE" >/dev/null 2>&1; then
  echo "没有名为 $REMOTE 的远程仓库，先看一眼 git remote -v。" >&2
  exit 2
fi

OLD_VERSION="$(current_version)"
echo "当前版本：${OLD_VERSION:-未知}"
echo "仓库目录：$REPO_DIR"

# ---------------------------------------------------------------- 拉取

echo "→ 检查 $REMOTE/$BRANCH …"
if ! git fetch --tags --prune --quiet "$REMOTE" 2>/tmp/mj-update-err.$$; then
  cat >&2 <<'EOF'
拉取失败。常见原因：
  · 网络不通 / 需要代理：报 "Failed to connect" 时先打开代理
  · 代理端口变了：git config --get "http.https://github.com.proxy"
  · 远程地址变了：git remote -v
EOF
  sed 's/^/    /' /tmp/mj-update-err.$$ >&2
  rm -f /tmp/mj-update-err.$$
  exit 1
fi
rm -f /tmp/mj-update-err.$$

if ! git rev-parse --verify --quiet "$REMOTE/$BRANCH" >/dev/null; then
  echo "远程没有 $BRANCH 分支，检查 MJ_UPDATE_BRANCH。" >&2
  exit 2
fi

BEHIND="$(git rev-list --count "HEAD..$REMOTE/$BRANCH" 2>/dev/null || echo 0)"
AHEAD="$(git rev-list --count "$REMOTE/$BRANCH..HEAD" 2>/dev/null || echo 0)"
NEW_VERSION="$(git show "$REMOTE/$BRANCH:mj/__init__.py" 2>/dev/null \
  | sed -n 's/^__version__ = "\(.*\)"/\1/p')"

if [ "$BEHIND" = "0" ]; then
  echo "✓ 已经是最新的（${OLD_VERSION:-未知}）"
  [ "$AHEAD" != "0" ] && echo "  本地有 $AHEAD 个提交还没推到远端。"
  exit 0
fi

echo "  有 $BEHIND 个新提交：${OLD_VERSION:-未知} → ${NEW_VERSION:-?}"

if [ "$CHECK_ONLY" = "1" ]; then
  echo
  echo "更新：./update.sh"
  exit 0
fi

# ---------------------------------------------------------------- 本地改动

if [ -n "$(git status --porcelain --untracked-files=no)" ]; then
  if [ "$FORCE" = "1" ]; then
    echo "⚠️  --force：丢弃本地对已跟踪文件的修改"
  else
    cat >&2 <<'EOF'

本地有未提交的改动，先处理一下（免得覆盖你的修改）：

    git stash          # 收起来，更新完 git stash pop
    git status         # 看看改了哪些文件

确认不要了就直接：

    ./update.sh --force
EOF
    exit 1
  fi
fi

# ---------------------------------------------------------------- 更新

OLD_SHA="$(git rev-parse HEAD)"

if [ "$FORCE" = "1" ]; then
  git reset --hard "$REMOTE/$BRANCH" >/dev/null || exit 1
elif ! git merge --ff-only "$REMOTE/$BRANCH" >/dev/null; then
  cat >&2 <<EOF

无法快进合并（本地有基于旧版本的提交）。两种选择：

    ./update.sh --force                  # 丢弃本地提交，直接对齐远端
    git rebase $REMOTE/$BRANCH           # 把你的提交挪到新版之上
EOF
  exit 1
fi

# 素材是否一起变了（画面/音效都在 assets/ 里，必须一起更新）
if ! git diff --quiet "$OLD_SHA" HEAD -- assets/ 2>/dev/null; then
  echo "  素材（assets/）也更新了，动画会跟着换成新版"
fi

# ---------------------------------------------------------------- 刷新安装

if [ -f ./install.sh ]; then
  echo "→ 刷新软链 / PATH"
  if out="$(bash ./install.sh 2>&1)"; then
    echo "  已刷新"
  else
    echo "  install.sh 返回非 0，输出如下（不影响代码已经更新）："
    printf '%s\n' "$out" | sed 's/^/    /' | head -8
  fi
fi

NEW_NOW="$(current_version)"
echo "✓ 更新完成：${OLD_VERSION:-未知} → ${NEW_NOW:-未知}"
echo "  直接敲 mj 就是新版本（软链没变，已打开的 shell 不用重开）"
