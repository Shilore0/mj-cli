# mj —— 命令行版透明蜘蛛侠彩蛋

敲 `mj`（或 `MJ`）回车，终端里会掉下来一只透明的 Q 版蜘蛛侠：各 50% 的独立概率，
要么「倒挂」着从天花板垂下来，要么「耍帅」挂着蛛丝比心。

Linux 命令行工具，Python 3 标准库实现，无第三方依赖。

```console
$ mj
```

## 长什么样

| 倒挂 | 耍帅 |
|---|---|
| ![倒挂](docs/preview-hang.png) | ![耍帅](docs/preview-pose.png) |

深色部分就是终端自己的背景——蜘蛛侠是「透明」的，只有像素落在终端底色上。
上面两张是 68 列最大档位的实际渲染结果（大终端才会用这一档）。

## 这个梗是什么

2026 年 7 月 29 日《蜘蛛侠：崭新之日》上映，8 月 1 日到 8 月 7 日抖音做了限时联动：
在**私信/群聊**里给好友发 `MJ`，屏幕会突然蹦出一只 Q 版蜘蛛侠——倒挂下来、比心、
朝你发射爱心。有说法认为还有「蜘蛛侠」「小蜘蛛」「彼得帕克」等关键词能触发不同动作。

`MJ` 是老粉的集体记忆：托比版的女友是玛丽·简（Mary Jane），荷兰弟版的女友是
米歇尔·琼斯（Michelle Jones），缩写都是 MJ。而《英雄无归》里奇异博士那道遗忘咒，
让全世界（包括 MJ）忘掉了彼得·帕克——于是「发一个 MJ 他就会来」这件事，
甜和虐是同时成立的。梗因此在评论区彻底跑偏：彩蛋本来只在私信生效，大家却在
任何视频下面刷 `MJ`，刷到最后平台紧急开了弹幕屏蔽。

这个项目把那个彩蛋搬到了终端里：不刷屏、不打扰别人，敲两个字母自己看。

## 安装

三种方式，任选其一。装完敲 `mj` 回车就有彩蛋。

### Linux（源码，改代码即时生效）

```bash
git clone https://github.com/Shilore0/mj-cli.git && cd mj-cli
./install.sh
```

`install.sh` 会把 `mj`、`MJ` 两个软链指向 `bin/mj`（默认装到 `~/.local/bin`，
可用 `MJ_BIN_DIR` 改），并提醒你把该目录加进 PATH。不装也能直接跑
`python3 bin/mj`。

要求：Linux + Python ≥ 3.8 + 支持 24 位真彩色的终端。

### Windows

要求：Windows 10 / 11 + Python 3.8 以上（安装 Python 时勾选
"Add python.exe to PATH"）。

**1. 拿到源码**：`git clone https://github.com/Shilore0/mj-cli.git`，或从 Releases
下载 zip 解压。

**2. 在源码目录跑一次安装脚本**（不需要管理员权限）：

```powershell
cd C:\path\to\mj-cli
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

**3. 新开一个 PowerShell 或 cmd 窗口**（PATH 和 profile 都只对新进程生效），验证：

```powershell
mj --version
mj            # 静音
MJ            # 带音乐
```

脚本只改当前用户的两处，都能一键撤销（见「彻底删除」）：

| 动作 | 位置 |
|---|---|
| 把 `bin` 加进**当前用户**的 PATH | 用户环境变量 `Path` |
| 写一个 `mj` 函数，用来区分 `MJ` / `mj` | Windows PowerShell 5.1 与 PowerShell 7 的 profile，两处都写 |

Windows 上的几点差别：

- **声音**走系统自带的 `winsound`，不用装 ffplay / paplay；`mj --explain` 里会显示
  `player : winsound`。
- **控制台**：推荐 Windows Terminal；传统 conhost 也能用（程序会临时开启 ANSI 转义，
  退出时还原）。
- **`--window` 不支持**：那是 Linux 的 GTK 悬浮窗，会提示一句后走终端模式。
- **中文乱码**：直接看没问题；把输出接到管道（`|`）时 PowerShell 会用 GBK 解码 UTF-8，
  先执行一次 `[Console]::OutputEncoding = [Text.Encoding]::UTF8`。

### deb / rpm

从 [Releases](https://github.com/Shilore0/mj-cli/releases) 下载，或用仓库里 `dist/` 的包：

```bash
sudo dpkg -i mj-cli_1.8-1_all.deb      # Debian / Ubuntu / Mint
sudo rpm -ivh mj-cli-1.8-1.noarch.rpm  # Fedora / RHEL / Rocky / openSUSE
```

装完 `/usr/bin/mj`、`/usr/bin/MJ` 都指向 `/usr/lib/mj-cli/bin/mj`，
程序与素材在 `/usr/lib/mj-cli/`，另有 man page（`man mj`）。

## 更新

先看当前版本：`mj --version`。

**一键更新（源码安装）**

仓库里带了更新脚本，拉代码 + 刷新安装一次搞定：

```bash
./update.sh              # 有更新就拉下来，再刷新软链
./update.sh --check      # 只看有没有新版本
./update.sh --force      # 本地改过代码也照样更新（丢弃改动）
```

```powershell
powershell -ExecutionPolicy Bypass -File .\update.ps1          # Windows
powershell -ExecutionPolicy Bypass -File .\update.ps1 -Check   # 只检查
```

脚本做的事：`git fetch` → 比较版本 → `git merge --ff-only` → 重跑 `install.sh` / `install.ps1`。
本地有未提交改动时会拒绝更新（提示你 `git stash`），确认不要了就加 `--force`。
素材（`assets/`）一起更新时会提示。

**手工更新**

```bash
cd mj-cli && git pull     # 软链没变，不需要重新安装
mj --version
```

**deb / rpm**

```bash
sudo dpkg -i mj-cli_1.8-1_all.deb          # 直接装新包就是升级
sudo rpm -Uvh mj-cli-1.8-1.noarch.rpm
```

> 涉及画面或素材的更新（例如 1.4 修掉的蛛丝）必须连 `assets/` 一起换：
> 更新脚本和 `git pull` 都自带，包方式是装新包。只换代码不换素材，画面还是旧的。

## 彻底删除

### 源码安装（Linux）

```bash
cd mj-cli
./uninstall.sh --purge     # 删 mj/MJ 两个软链 + 清掉 ~/.bashrc 里的 PATH 行（自动备份）
hash -r                    # 刷新 bash 的命令缓存，否则可能还提示"未找到"
command -v mj || echo 已清干净
rm -rf mj-cli              # 连代码一起删
```

不用脚本的话，等价手写：

```bash
rm -f ~/.local/bin/mj ~/.local/bin/MJ
sed -i '/\.local\/bin/d' ~/.bashrc
hash -r
```

### 源码安装（Windows）

```powershell
cd C:\path\to\mj-cli
powershell -ExecutionPolicy Bypass -File .\uninstall.ps1
```

它会把 `bin` 从**用户 PATH** 里移除，并删掉两个 PowerShell profile 里的 `mj` 函数块
（删完开新窗口验证）。之后直接删掉整个文件夹即可。

### deb / rpm

```bash
sudo dpkg -r mj-cli          # 连配置一起清：sudo dpkg --purge mj-cli
sudo rpm -e mj-cli
```

确认删干净：

```bash
command -v mj || echo 命令已移除
ls /usr/lib/mj-cli 2>/dev/null || echo 目录已删除
```

## 用法

```console
$ mj                 # 抽一次：50% 倒挂 / 50% 耍帅
$ MJ                 # 同上，大写也认
$ mj mjmjmj          # 连发：写了 3 个 mj，就连续播 3 次
$ mj mj mj           # 同上，分开写也算 3 次
$ mj --repeat 3      # 也是连播 3 次
$ mj hang            # 不看抽签结果，直接放「倒挂」
$ mj pose            # 直接放「耍帅」
$ mj --audio         # 小写 mj 默认静音，这样才出声
$ mj --no-audio      # 大写 MJ 默认有音乐，这样才安静
$ mj --size 50       # 限制精灵宽度（档位 18/26/36/50/68 列）
$ mj --theme light   # 浅色终端用这一版（预渲染时就分了两套）
$ mj --window        # 开一个真正透明的桌面悬浮窗（见下）
$ mj --list          # 看看有哪些彩蛋、多少帧、支持哪些尺寸
$ mj --pick-only     # 只抽签不播放，用来验证概率
$ mj --explain       # 打印抽到什么、有没有声音、用哪个素材
$ mj --where         # 打印装在哪：程序目录、启动器、素材、Python、音频后端
```

| 参数 | 说明 |
|---|---|
| `mj` 串（如 `mjmjmj`） | 连发，每个 `mj` 播一次（大小写都行，`MJMJ` = 2 次） |
| `hang` / `pose` | 指定彩蛋，跳过随机；写几次就播几次 |
| `--repeat N` / `-n N` | 把整串再重复 N 遍 |
| `--list` | 列出彩蛋、帧数、尺寸档位 |
| `--pick-only` | 只输出抽到的结果（脚本/测试友好） |
| `--explain` | 不播放，打印彩蛋、声音开关及理由、音轨与播放器等 |
| `--where` | 打印安装位置（排查「装到哪去了」用） |
| `--audio` / `--sound` | 强制出声（小写 `mj` 默认静音） |
| `--no-audio` | 强制静音（大写 `MJ` 默认有音乐） |
| `--size N` | 精灵宽度上限（字符列数） |
| `--theme dark\|light` | 按深色/浅色终端预渲染的版本，默认 `dark` |
| `--fps F` | 覆盖帧率，默认 30 |
| `--window` | 透明悬浮窗模式，失败自动退回终端 |
| `--opacity X` | 窗口模式整体不透明度（0–1） |
| `--seed N` | 固定随机种子，仅测试用 |
| `--force` | 输出被重定向时也照样渲染 |

被重定向（`mj | cat`）时不会往管道里塞几兆转义序列，只打印名字（连发时用 `、` 连起来）。

### 连发

跟抖音里发消息一样，**写几个 `mj` 就播几次**，每次独立抽签（可能连着两次都是「倒挂」）：

```console
$ mj mjmj        # 2 次
$ mj mjmjmj      # 3 次
$ mj MJ MJ       # 2 次，且带音乐（大写）
$ mj --repeat 5  # 5 次
```

`--pick-only` 连发时一行输出一次（`wc -l` 就是次数），`--explain` 会显示 `sends: N 次连发`。

## 声音：大小写决定

| 调用 | 默认 | 想反过来 |
|---|---|---|
| `mj`（小写） | 静音 | `mj --audio` |
| `MJ`（大写） | 带音乐 | `MJ --no-audio` |

两个名字指向同一份程序，程序只看**自己被叫什么名字**，不看参数。
所以你在公共终端、会上投屏的时候敲小写，自己玩的时候敲大写。
（Windows 上命令名不区分大小写，启动器 / profile 函数会把原始大小写通过 `MJ_AS`
传给程序，行为与 Linux 一致。）

音轨跟动画是写死绑定的，不会串：

| 彩蛋 | 音轨 | 来源 |
|---|---|---|
| 倒挂 `hang` | `hang.wav` | `蜘蛛侠-倒挂/3/output.mp4` 的音轨 |
| 耍帅 `pose` | `pose.wav` | `蜘蛛侠-耍帅/2/output.mp4` 的音轨 |

构建素材时会用 PCM 逐字节摘要校验「这个 wav 是不是这条源片的声音」，对不上直接报错，
防止以后换素材悄悄错配。`mj --explain` 可以随时查看当前抽到的彩蛋用的是哪条音轨。

实际出声要有播放器：Windows 用系统自带的 `winsound`；Linux / macOS 用
`pw-play` / `paplay` / `aplay` / `ffplay` / `mpv` / `sox` 任意一个，都没有就静音播放
（动画照常）。也可以 `MJ_AUDIO_CMD=...` 指定自己的命令。

## 两种播放模式

**终端模式（默认）**：用真彩色半块字符（`▀` / `▄`）把每两行像素压进一个字符格，
透明像素留空——终端底色直接透出来，这就是命令行里的「透明」。整段动画画在备用
屏幕上，退出时（包括 `Ctrl+C`）恢复原样，不弄脏你的 shell。

**透明悬浮窗（`--window`）**：调用 PyGObject 开一个无边框、置顶、鼠标穿透的
ARGB 窗口，ffmpeg 解码带 alpha 的 VP9 直接交给 cairo 合成，是逐像素真透明。
需要 `python3-gi`、`python3-gi-cairo`、`ffmpeg` 和一个带合成器的桌面；
Wayland 下窗口位置由合成器决定，可能不会正好居中。跑不起来会自动退回终端模式。

## 为什么不卡

帧不在运行时画。构建素材时就把每一帧渲染成了完整的 ANSI 字符串（含颜色），
`assets/terminal/*.bin` 里存的是 zlib 压缩后的文本。播放时每帧只做三件事：

1. `zlib.decompress` 解压一帧文本；
2. 按 `\n` 切开；
3. 每行前面拼一个光标定位转义，一次性写入 stdout。

实测（68 列最大档位）每帧 0.07–0.13 ms，CPU 基本为零；剩下的时间全在
`time.sleep` 里等 30 fps 的节拍，所以机器慢也不会掉帧。

尺寸是离散档位（18/26/36/50/68 列），运行时按终端大小挑一个放得下的最大档，
只做定位不做缩放——同一份字符串在任何屏幕上都是同一张图。

## 素材构建

两组源视频是 Side-by-Side Alpha（左半亮度遮罩、右半 RGB），放在 `source/`：

| 素材 | 源尺寸 | 时长 / 帧率 | Alpha 联合范围 | 裁剪结果 |
|---|---:|---:|---:|---|
| 倒挂 `source/hang/output.mp4` | 2144×2352 | 3.05s / 30fps | x=203..790, y=0..1587 | 638×1612+178+0 |
| 耍帅 `source/pose/output.mp4` | 2160×2336 | 3.01s / 30fps | x=0..1079, y=0..1569 | 1080×1594+0+0 |

```bash
python3 scripts/build_assets.py            # 全量构建
python3 scripts/build_assets.py --no-webm  # 跳过较慢的 VP9 透明编码
FFMPEG_PATH=/usr/bin/ffmpeg python3 scripts/build_assets.py
```

脚本会：计算整段遮罩的联合包围盒（外扩 24px）→ 用 `alphamerge` 合成 RGBA →
产出带 alpha 的 VP9 webm（窗口模式用）、48kHz wav（音效），以及每个彩蛋
5 档宽度 × 2 套主题的预渲染 ANSI 帧包。需要 ffmpeg，`ffprobe` 可选。

> 注意：VP9 的 alpha 是独立的一层，用 ffmpeg 读的时候必须显式加
> `-c:v libvpx-vp9`，否则拿到的是不透明画面。构建脚本和窗口模式都带了这个参数。

产物（`assets/`）：

| 文件 | 说明 |
|---|---|
| `spiderman-{hang,pose}.webm` | 带透明通道的 VP9，供窗口模式实时解码 |
| `{hang,pose}.wav` | 48kHz / 16bit 立体声音轨 |
| `terminal/{hang,pose}.bin` | 深色主题的预渲染 ANSI 帧包（≈2.2MB） |
| `terminal/{hang,pose}.light.bin` | 浅色主题版本 |
| `terminal/index.json` | 每帧的压缩偏移与长度、各档位尺寸 |
| `manifest.json` | 运行期清单 |

`assets/` 已随本目录一起提供，**不重新构建也能直接跑**。

## 目录结构

```text
mj-cli/
├─ bin/mj                     # 启动器（install.sh 软链到 PATH）
├─ mj/
│  ├─ cli.py                  # 参数解析与流程编排
│  ├─ manifest.py             # 素材清单、50/50 抽签
│  ├─ term.py                 # 终端播放（只解压 + 输出）
│  ├─ render_cells.py         # 构建期的像素→ANSI 渲染器
│  ├─ window.py               # 可选：透明悬浮窗
│  └─ audio.py                # 音效播放（paplay/pw-play/aplay/ffplay/mpv…）
├─ scripts/build_assets.py    # 素材构建
├─ packaging/
│  ├─ build_packages.py       # 手写 deb / rpm 打包器（纯 Python）
│  ├─ smoke-test.sh           # 安装→校验→卸载自检脚本
│  └─ TESTING.md              # 打包与测试说明
├─ dist/                      # 打好的 deb / rpm
├─ source/{hang,pose}/        # Side-by-Side Alpha 源片
├─ assets/                    # 构建产物（已提供）
├─ docs/                      # README 预览图
├─ tests/test_mj.py           # 单元测试
├─ bin/mj.cmd                 # Windows 启动器（cmd / PowerShell）
├─ install.sh / uninstall.sh   # Linux（软链）
├─ install.ps1 / uninstall.ps1 # Windows（改用户 PATH 与 profile）
├─ update.sh / update.ps1      # 从 GitHub 一键更新
├─ Makefile                   # make test / assets / package / smoke
├─ .github/workflows/         # CI（测试+打包+真装）与发版
└─ README.md / RELEASING.md / CONTRIBUTING.md / CHANGELOG.md / LICENSE / THIRD_PARTY_NOTICES.md
```

## 打包（维护者）

两个包内容一致（`all` / `noarch`），都装到 `/usr/lib/mj-cli/`，`/usr/bin` 下只放软链：

| 文件 | 适用 |
|---|---|
| `mj-cli_1.8-1_all.deb` | Debian / Ubuntu / Mint / Kali … |
| `mj-cli-1.8-1.noarch.rpm` | Fedora / RHEL / Rocky / Alma / openSUSE … |

打包器是手写的（`ar` + `tar` + `cpio` + RPM header），不需要 `dpkg-deb`、
`rpmbuild`、`fpm`，Windows 上也能出包：

```bash
python3 packaging/build_packages.py --verify   # 打两个 + 解开自检
python3 packaging/build_packages.py --deb      # 只打 deb
```

在真实 Linux 上跑完整的安装 / 校验 / 卸载：`bash packaging/smoke-test.sh`，
细节见 [packaging/TESTING.md](packaging/TESTING.md)；发版流程见
[RELEASING.md](RELEASING.md)（推 `v*` tag 会自动打包并发布到 Releases）。

## 测试与开发

```bash
make test        # 或 python3 -m unittest discover -s tests -v
make package     # 打 deb/rpm 并自检
make smoke       # 在 Linux 上装一遍、验一遍、卸掉
```

改了渲染逻辑（`mj/render_cells.py`）或换了源片，要跑 `make assets` 重建帧包，
否则包里的画面还是旧的。贡献流程见 [CONTRIBUTING.md](CONTRIBUTING.md)。

测试覆盖：抽签分布（4000 次）、允许连击、尺寸档位是否放得下、帧包几何
（每帧行数/列宽）、深浅两套主题是否都构建了、渲染器对全透明/不透明帧的输出、
「小写静音 / 大写带音乐」的判定与参数优先级。

## 平台说明

- 终端模式 Linux / macOS / Windows 都能跑；Linux 与 Windows（PowerShell / Windows Terminal）
  已实测，macOS 未针对验收。
- Windows 上用系统自带的 `winsound` 播放音效；Linux / macOS 上挑 PATH 里的
  `pw-play` / `paplay` / `aplay` / `ffplay` / `mpv`，都没有就静音播放。
- macOS 的 Terminal.app 不支持 24 位色（可改用 iTerm2 / WezTerm / kitty）。
- 终端模式无法覆盖在其他窗口之上——它画在终端自己的屏幕缓冲区里。想要真正
  盖在桌面上的效果，用 `--window`。

## 素材与归属

两组源视频取自 [MI-KUNs/CN-TikTok-MJ](https://github.com/MI-KUNs/CN-TikTok-MJ)
（Apache License 2.0），内容据称来自抖音官方彩蛋，上游未提供进一步权属证明。

抖音、Spider-Man 及相关名称、角色、声音和素材的权利归各自权利人所有。本项目为
非官方、非商业的技术演示，与字节跳动、抖音、Marvel 或 Sony 无隶属、授权或背书
关系。公开分发前请自行确认素材使用符合适用法律、平台规则和权利人要求。

完整说明见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

## License

代码采用 [Apache License 2.0](LICENSE)。第三方素材同时受其来源、相关权利人及
适用法律约束，详见第三方声明。
