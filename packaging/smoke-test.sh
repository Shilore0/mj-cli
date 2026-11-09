#!/usr/bin/env bash
# 在 Linux 上跑一遍完整的 安装 → 功能 → 卸载 流程。
#
#   bash packaging/smoke-test.sh          # 自动识别 dpkg / rpm
#   bash packaging/smoke-test.sh --no-uninstall
#
# 有失败项时退出码非 0。sudo 会用到的只有安装/卸载，其余都是普通用户操作。

set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DIST="$(dirname "$HERE")/dist"
DO_UNINSTALL=1
[ "${1:-}" = "--no-uninstall" ] && DO_UNINSTALL=0

fail=0
pass=0
fail_list=()

step() { printf '\n\033[1;36m== %s ==\033[0m\n' "$*"; }
ok()   { pass=$((pass + 1)); printf '  \033[32mok\033[0m   %s\n' "$*"; }
bad()  { fail=$((fail + 1)); fail_list+=("$*"); printf '  \033[31mFAIL\033[0m %s\n' "$*"; }
need() { if eval "$2" >/dev/null 2>&1; then ok "$1"; else bad "$1"; fi; }

command -v python3 >/dev/null || { echo "缺少 python3"; exit 2; }
echo "python3: $(python3 -V 2>&1)"

if command -v dpkg >/dev/null; then
  DEB=$(ls "$DIST"/mj-cli_*_all.deb 2>/dev/null | head -1)
  [ -n "$DEB" ] || { echo "找不到 deb：$DIST"; exit 2; }
  echo "包：$(basename "$DEB")"

  step "安装"
  sudo dpkg -i "$DEB" || { echo "dpkg 报错，尝试补依赖"; sudo apt-get -f install -y; }
  hash -r   # 新装的命令要刷哈希，否则 command -v 可能查不到

  step "包信息"
  need "dpkg 状态为已安装" "dpkg -s mj-cli | grep -q 'Status: install ok installed'"
  need "版本 1.4-1" "dpkg-query -W -f='\${Version}' mj-cli | grep -qx 1.4-1"
  need "架构 all" "dpkg-query -W -f='\${Architecture}' mj-cli | grep -qx all"
  need "依赖声明包含 python3" "dpkg -s mj-cli | grep -q 'Depends:.*python3'"
  need "文件清单包含 /usr/lib/mj-cli/mj/cli.py" "dpkg -L mj-cli | grep -qx /usr/lib/mj-cli/mj/cli.py"
  need "man page 已安装" "test -f /usr/share/man/man1/mj.1.gz"
  echo "  ---- 最近安装记录 ----"
  grep -h "mj-cli" /var/log/dpkg.log 2>/dev/null | tail -2 | sed 's/^/  /'

  step "运行"
  need "/usr/bin/mj 存在且可执行" "test -x /usr/bin/mj"
  need "/usr/bin/MJ 指向同一目标" "test \"\$(readlink -f /usr/bin/MJ)\" = \"\$(readlink -f /usr/bin/mj)\""
  need "mj --version" "mj --version | grep -q '1.4'"
  need "mj --list 有两个彩蛋" "mj --list | grep -q hang && mj --list | grep -q pose"
  need "mj --pick-only 输出合法" "mj --pick-only | grep -qE '^(hang|pose)'"
  need "MJ --pick-only 大写也能跑" "MJ --pick-only | grep -qE '^(hang|pose)'"
  need "音轨绑定：倒挂→hang.wav" "mj --list | grep hang | grep -q hang.wav"
  need "音轨绑定：耍帅→pose.wav" "mj --list | grep pose | grep -q pose.wav"
  need "mj（小写）默认静音" "mj --explain | grep -q 'sound  : off'"
  need "MJ（大写）默认带音乐" "MJ --explain | grep -q 'sound  : on'"
  need "mj --audio 能开声音" "mj --audio --explain | grep -q 'sound  : on'"
  need "MJ --no-audio 能关声音" "MJ --no-audio --explain | grep -q 'sound  : off'"
  need "素材完整" "test -f /usr/lib/mj-cli/assets/terminal/index.json"
  echo "  ---- 连抽 10 次（应大小写都有、允许连击）----"
  for _ in $(seq 10); do printf '%s ' "$(mj --pick-only | cut -f1)"; done; echo
  echo "  ---- 实际播放一次（约 3 秒，静音）----"
  if mj --no-audio --force >/tmp/mj-smoke.ansi 2>/tmp/mj-smoke.err; then
    ok "播放完成"
    need "输出包含备用屏幕与光标恢复序列" "grep -qa $'\x1b\[?1049h' /tmp/mj-smoke.ansi && grep -qa $'\x1b\[?1049l' /tmp/mj-smoke.ansi"
    printf '  输出 %s 字节\n' "$(wc -c </tmp/mj-smoke.ansi)"
  else
    bad "播放失败：$(cat /tmp/mj-smoke.err)"
  fi

  if [ "$DO_UNINSTALL" = 1 ]; then
    step "卸载"
    sudo dpkg -r mj-cli
    hash -r   # 删掉之后同样要刷，否则缓存里还留着旧路径
    need "命令已移除" "! type -P mj"
    need "/usr/lib/mj-cli 已删除" "test ! -d /usr/lib/mj-cli"
    need "dpkg 列表里已无此包" "! dpkg -l mj-cli 2>/dev/null | grep -q '^ii'"
  fi

elif command -v rpm >/dev/null; then
  RPM=$(ls "$DIST"/mj-cli-*.noarch.rpm 2>/dev/null | head -1)
  [ -n "$RPM" ] || { echo "找不到 rpm：$DIST"; exit 2; }
  echo "包：$(basename "$RPM")"

  step "检查包（安装前）"
  need "rpm -qip 可读" "rpm -qip '$RPM' | grep -q 'Name.*: mj-cli'"
  need "rpm -qlp 能列出文件" "rpm -qlp '$RPM' | grep -q '/usr/bin/mj'"
  need "载荷可被 libarchive/rpm2cpio 解出" "rpm2cpio '$RPM' | cpio -t 2>/dev/null | grep -q './usr/lib/mj-cli/mj/cli.py'"

  step "安装"
  sudo rpm -ivh "$RPM"
  hash -r

  step "包信息"
  need "已安装" "rpm -q mj-cli"
  need "版本 1.4" "rpm -q --qf '%{VERSION}' mj-cli | grep -qx 1.4"
  need "架构 noarch" "rpm -q --qf '%{ARCH}' mj-cli | grep -qx noarch"
  need "文件清单包含 /usr/lib/mj-cli/mj/cli.py" "rpm -ql mj-cli | grep -qx /usr/lib/mj-cli/mj/cli.py"

  step "校验（最关键：rpm -V 会逐个比对摘要/权限/符号链接）"
  if out=$(rpm -V mj-cli 2>&1); then
    if [ -z "$out" ]; then ok "所有文件的摘要、大小、权限、属主一致"; else echo "$out" | sed 's/^/  /'; bad "rpm -V 有输出"; fi
  else
    bad "rpm -V 失败"
  fi

  step "运行"
  need "mj --version" "mj --version | grep -q '1.4'"
  need "mj --list 有两个彩蛋" "mj --list | grep -q hang && mj --list | grep -q pose"
  need "mj --pick-only 输出合法" "mj --pick-only | grep -qE '^(hang|pose)'"
  need "MJ --pick-only 大写也能跑" "MJ --pick-only | grep -qE '^(hang|pose)'"
  need "音轨绑定：倒挂→hang.wav" "mj --list | grep hang | grep -q hang.wav"
  need "音轨绑定：耍帅→pose.wav" "mj --list | grep pose | grep -q pose.wav"
  need "mj（小写）默认静音" "mj --explain | grep -q 'sound  : off'"
  need "MJ（大写）默认带音乐" "MJ --explain | grep -q 'sound  : on'"
  need "mj --audio 能开声音" "mj --audio --explain | grep -q 'sound  : on'"
  need "MJ --no-audio 能关声音" "MJ --no-audio --explain | grep -q 'sound  : off'"
  for _ in $(seq 10); do printf '%s ' "$(mj --pick-only | cut -f1)"; done; echo
  if mj --no-audio --force >/tmp/mj-smoke.ansi 2>/tmp/mj-smoke.err; then
    ok "播放完成（$(wc -c </tmp/mj-smoke.ansi) 字节）"
  else
    bad "播放失败：$(cat /tmp/mj-smoke.err)"
  fi

  if [ "$DO_UNINSTALL" = 1 ]; then
    step "卸载"
    sudo rpm -e mj-cli
    hash -r
    need "命令已移除" "! type -P mj"
    need "/usr/lib/mj-cli 已删除" "test ! -d /usr/lib/mj-cli"
  fi

else
  echo "这台机器既没有 dpkg 也没有 rpm，没法测包。"
  exit 2
fi

printf '\n\033[1m结果：%d 项通过，%d 项失败\033[0m\n' "$pass" "$fail"

if [ "$fail" -ne 0 ]; then
  # 这两行是 GitHub Actions 的注解指令，CI 里能直接在页面上看到失败项
  for item in "${fail_list[@]}"; do
    printf '::error title=smoke-test::%s\n' "$item"
  done
  exit 1
fi
exit 0
