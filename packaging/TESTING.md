# 测这两个包

产物在 `dist/`：

| 文件 | 大小 | 适用 |
|---|---:|---|
| `mj-cli_1.7-1_all.deb` | 7.2 MB | Debian / Ubuntu / Mint / Kali … |
| `mj-cli-1.7-1.noarch.rpm` | 7.2 MB | Fedora / RHEL / Rocky / Alma / openSUSE … |

两个包内容一致，`Architecture: all` / `BuildArch: noarch`（纯 Python）。
装完后的布局：

```
/usr/bin/mj            -> /usr/lib/mj-cli/bin/mj
/usr/bin/MJ            -> /usr/lib/mj-cli/bin/mj
/usr/lib/mj-cli/       mj/*.py + assets/（预渲染帧包 7.6MB）
/usr/share/doc/mj-cli/ README.md、copyright、THIRD_PARTY_NOTICES.md
/usr/share/man/man1/mj.1.gz
```

## 一行命令

把整个 `mj-cli` 目录（或至少 `dist/` + `packaging/smoke-test.sh`）放到 Linux 机器上，然后：

```bash
bash packaging/smoke-test.sh          # 装 → 检查 → 播放 → 卸载，全自动
bash packaging/smoke-test.sh --no-uninstall   # 想留着重看效果
```

脚本会自动识别 dpkg 还是 rpm，最后打印「N 项通过，M 项失败」。

## 手动流程

### Debian / Ubuntu

```bash
sudo dpkg -i mj-cli_1.7-1_all.deb
dpkg -L mj-cli | head                 # 看文件清单
mj --version && mj --list
mj                                    # 真看一眼
sudo dpkg -r mj-cli                   # 卸载
```

`dpkg -i` 如果报依赖问题（极少见，只依赖 `python3 (>= 3.8)`）：

```bash
sudo apt-get -f install -y
```

### Fedora / RHEL / openSUSE

```bash
sudo rpm -ivh mj-cli-1.7-1.noarch.rpm
rpm -qi mj-cli                        # 元信息
rpm -ql mj-cli | head                 # 文件清单
rpm -V mj-cli                         # 逐个文件校验摘要/权限，无输出=全部一致
mj --version && mj
sudo rpm -e mj-cli                    # 卸载
```

## 应该看到什么

- `mj --list` 输出两行：`hang 倒挂 … 18x23/26x33/36x45/50x63/68x86`、`pose 耍帅 …`。
- `mj` 在终端里画出一只透明蜘蛛侠（3 秒），结束后**屏幕恢复原样**，光标回来。
- 多敲几次 `mj`，「倒挂」「耍帅」随机出现，允许连续两次一样（这是设计，不是 bug）。
- **小写 `mj` 没声音、大写 `MJ` 有声音**——这是设计，不是 bug。
  反过来用 `mj --audio` / `MJ --no-audio`。`mj --explain` 会直接告诉你这次的判定结果。
- `mj --no-audio | cat` 只打印一行名字，不会往管道里灌转义序列。

## 已知限制（不算 bug）

- **没声音**：包不强行依赖音频工具。装了 `ffplay` / `paplay` / `pw-play` / `aplay` / `mpv`
  其中之一就会出声，都没有就静音播放。`mj --explain` 的 `player` 一行会说明。
- **`--window` 用不了**：需要 `python3-gi`、`python3-gi-cairo` 和一个带合成器的桌面。
  缺了会打印一行提示并自动退回终端模式，不影响默认用法。
- **终端要支持真彩色**：`echo $COLORTERM` 一般是 `truecolor`。macOS Terminal.app 不支持
  （VM 里不涉及）。老式 256 色终端会显示成近似色。
- **终端太小**：会自动选最小的档位并裁掉底部，能看但不完整。放大窗口（或 `--size 26`）更好。

## 要我修 bug 的话，把这些贴回来

```bash
cat /etc/os-release
uname -m && python3 -V && echo "$TERM / $COLORTERM"
sudo dpkg -i …deb 2>&1        # 或 sudo rpm -ivh …rpm 2>&1
rpm -V mj-cli 2>&1            # rpm 系
dpkg -s mj-cli 2>&1           # deb 系
mj --list 2>&1 && mj --pick-only 2>&1
```

## 自己重新打包

```bash
python3 packaging/build_packages.py           # 两个都打
python3 packaging/build_packages.py --deb     # 只打 deb
python3 packaging/build_packages.py --rpm     # 只打 rpm
python3 packaging/build_packages.py --verify  # 打完自检（解开包逐项比对）
```

打包器是纯 Python（`ar` + `tar` + `cpio` + RPM header 手写），不需要 `dpkg-deb`、
`rpmbuild`、`fpm`，Windows / macOS 上也能出包。版本号取自 `mj/__init__.py`。
