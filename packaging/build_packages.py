#!/usr/bin/env python3
"""把 mj-cli 打成 .deb 和 .rpm —— 纯 Python，不依赖 dpkg-deb / rpmbuild。

这两个格式看着唬人，其实都能手写：

  deb = ar 归档，里面三件：debian-binary、control.tar.gz、data.tar.xz
  rpm = lead(96B) + 签名头 + 主头 + xz 压缩的 cpio 载荷

所以在 Windows / macOS 上也能出包，产物跟 Linux 原生工具做出来的一样能被
dpkg -i / rpm -i 安装。想改用发行版的原生流程（dpkg-buildpackage / rpmbuild），
把这里生成的清单当参考即可。

用法：
    python3 packaging/build_packages.py            # 两个都打
    python3 packaging/build_packages.py --deb      # 只打 deb
    python3 packaging/build_packages.py --rpm      # 只打 rpm
    python3 packaging/build_packages.py --verify   # 打完后自检（会解开包读一遍）
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import lzma
import os
import re
import struct
import sys
import tarfile
import time
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"

PKG_NAME = "mj-cli"
SUMMARY = "命令行版透明蜘蛛侠彩蛋（抖音「MJ」梗）"
MAINTAINER = "mj-cli maintainers <noreply@example.invalid>"
SECTION = "games"
LICENSE = "Apache-2.0"
GROUP = "Applications/System"
# 包的 Homepage 字段。换仓库时改这里，或用 MJ_HOMEPAGE 环境变量覆盖。
URL = os.environ.get("MJ_HOMEPAGE", "https://github.com/Shilore0/mj-cli")
DESCRIPTION = """\
敲 mj（或 MJ）回车，终端里会掉下来一只透明的 Q 版蜘蛛侠：各 50% 的独立概率
播放「倒挂」或「耍帅」。用真彩色半块字符渲染，透明像素留空，让终端背景透出来。
帧在构建期就预渲染成 ANSI 字符串，播放时只做解压和输出，CPU 占用可以忽略。
"""

# 安装布局：程序本体放 /usr/lib/mj-cli，/usr/bin 下只放两个软链
LIBDIR = "/usr/lib/mj-cli"
DOCDIR = f"/usr/share/doc/{PKG_NAME}"
MANDIR = "/usr/share/man/man1"
BIN_LINKS = [("mj", f"{LIBDIR}/bin/mj"), ("MJ", f"{LIBDIR}/bin/mj")]

# 不装进包里的东西：源片、测试、构建脚本、预览图、缓存
EXCLUDE_DIRS = {"source", "tests", "scripts", "docs", "packaging", "dist", "__pycache__"}
EXCLUDE_SUFFIX = {".pyc", ".pyo"}

MTIME = 1762700400  # 2026-11-09T21:40:00+08:00，固定下来让构建可复现


# ---------------------------------------------------------------- 文件清单


@dataclass
class Entry:
    path: str                      # 包内绝对路径，如 /usr/lib/mj-cli/mj/cli.py
    kind: str                      # "dir" | "file" | "link"
    mode: int
    data: bytes = b""
    link: str = ""

    @property
    def size(self) -> int:
        if self.kind == "file":
            return len(self.data)
        if self.kind == "link":
            return len(self.link.encode())
        return 0

    @property
    def digest(self) -> str:
        return hashlib.md5(self.data).hexdigest() if self.kind == "file" else ""


def version() -> tuple[str, int]:
    text = (ROOT / "mj" / "__init__.py").read_text("utf-8")
    match = re.search(r'__version__\s*=\s*"([^"]+)"', text)
    if not match:
        raise SystemExit("读不到 mj/__init__.py 里的 __version__")
    full = match.group(1)
    release = re.search(r'-(\d+)$', full)
    if release:
        return full[: release.start()], int(release.group(1))
    return full, 1


def man_page(ver: str) -> bytes:
    """生成 gzip 压缩的 man page（/usr/share/man/man1/mj.1.gz）。"""
    text = f""".TH MJ 1 "2026-11-09" "mj-cli {ver}" "User Commands"
.SH NAME
mj \\- 命令行版「透明蜘蛛侠」彩蛋
.SH SYNOPSIS
.B mj
[\\fIhang\\fR|\\fIpose\\fR] [\\fI选项\\fR]
.br
.B MJ
[\\fI选项\\fR]
.SH DESCRIPTION
每次运行独立掷一次硬币，各 50% 的概率播放「倒挂」或「耍帅」的透明蜘蛛侠。
动画用真彩色半块字符画在终端的备用屏幕上，透明像素留空，让终端背景透出来；
退出（包括 Ctrl+C）后恢复原屏幕。
.PP
帧在构建素材时就预渲染成 ANSI 字符串，运行期只做解压与输出，几乎不占 CPU。
.SH 声音与大小写
默认行为由调用名的大小写决定：
.TP
.B mj
（小写）默认静音。要声音请加
.B \\-\\-audio
。
.TP
.B MJ
（大写）默认带音乐。想安静请加
.B \\-\\-no-audio
。
.PP
音轨与动画是一一绑定的：「倒挂」固定用 hang.wav，「耍帅」固定用 pose.wav，
构建素材时会用 PCM 摘要校验两者的对应关系。
.SH OPTIONS
.TP
.B hang
强制播放「倒挂」。
.TP
.B pose
强制播放「耍帅」。
.TP
.B \\-\\-list
列出可用彩蛋、帧数、音轨与尺寸档位后退出。
.TP
.B \\-\\-pick-only
只输出抽签结果，不播放（便于脚本和统计）。
.TP
.B \\-\\-explain
不播放，打印这次抽到的彩蛋、声音开关及理由、音轨与播放器。
.TP
.B \\-\\-where
打印安装位置：程序目录、启动器、素材目录、Python 解释器与音频后端。
.TP
.B \\-\\-audio
强制播放音效（小写 mj 默认静音，用它开声音）。也可以写成
.B \\-\\-sound
。
.TP
.B \\-\\-no-audio
强制静音（大写 MJ 默认带音乐，用它关掉）。
.TP
.B \\-\\-size \\fIN\\fR
限制精灵宽度为 N 列（档位 18/26/36/50/68）。
.TP
.B \\-\\-theme \\fIdark\\fR|\\fIlight\\fR
选择按深色或浅色终端预渲染的版本，默认 dark。
.TP
.B \\-\\-fps \\fIF\\fR
覆盖帧率，默认 30。
.TP
.B \\-\\-window
用透明的桌面悬浮窗播放（需要 PyGObject 与合成器），失败自动退回终端。
.TP
.B \\-\\-opacity \\fIX\\fR
窗口模式的整体不透明度（0\\-1）。
.TP
.B \\-\\-force
输出不是终端时也强制渲染。
.SH ENVIRONMENT
.TP
.B MJ_ASSETS
覆盖素材目录。
.TP
.B MJ_AUDIO_CMD
指定播放音效的命令。
.TP
.B MJ_AS
启动器用它传递「实际敲的是 mj 还是 MJ」——Windows 的命令名不区分大小写，
需要这样把原始大小写带进来。
.PP
Windows 下用系统自带的 winsound 播放音效；Linux / macOS 下挑 PATH 里的
pw-play、paplay、aplay、ffplay、mpv 或 sox。
.SH FILES
.TP
.I /usr/lib/mj-cli/
程序与素材。
.SH SEE ALSO
.BR ffplay (1),
.BR paplay (1)
.SH AUTHOR
mj-cli maintainers。素材与角色权利归各自权利人，本项目是非官方技术演示。
"""
    buffer = io.BytesIO()
    with gzip.GzipFile(fileobj=buffer, mode="wb", mtime=0, compresslevel=9) as handle:
        handle.write(text.encode("utf-8"))
    return buffer.getvalue()


def collect(ver: str) -> list[Entry]:
    entries: list[Entry] = []
    dirs: set[str] = {"/usr", "/usr/bin", "/usr/lib", "/usr/share",
                      "/usr/share/doc", DOCDIR, "/usr/share/man", MANDIR, LIBDIR,
                      f"{LIBDIR}/bin", f"{LIBDIR}/assets"}

    def add_file(rel_source: Path, target: str, mode: int = 0o644) -> None:
        entries.append(Entry(target, "file", mode, data=rel_source.read_bytes()))
        parent = str(Path(target).parent).replace("\\", "/")
        dirs.add(parent)

    add_file(ROOT / "bin" / "mj", f"{LIBDIR}/bin/mj", 0o755)

    for path in sorted((ROOT / "mj").rglob("*")):
        if path.is_dir() or path.suffix in EXCLUDE_SUFFIX:
            continue
        add_file(path, f"{LIBDIR}/mj/{path.relative_to(ROOT / 'mj').as_posix()}")

    # 素材：除了构建期的源片，全都装
    for path in sorted((ROOT / "assets").rglob("*")):
        if path.is_dir():
            continue
        add_file(path, f"{LIBDIR}/assets/{path.relative_to(ROOT / 'assets').as_posix()}")

    add_file(ROOT / "README.md", f"{DOCDIR}/README.md")
    add_file(ROOT / "LICENSE", f"{DOCDIR}/copyright")
    add_file(ROOT / "THIRD_PARTY_NOTICES.md", f"{DOCDIR}/THIRD_PARTY_NOTICES.md")
    entries.append(Entry(f"{MANDIR}/mj.1.gz", "file", 0o644, data=man_page(ver)))

    for name, target in BIN_LINKS:
        entries.append(Entry(f"/usr/bin/{name}", "link", 0o777, link=target))

    # 目录条目补齐（cpio 里要有，deb 里也要有）
    for directory in dirs:
        if directory in ("/", ""):
            continue
        entries.append(Entry(directory, "dir", 0o755))

    # 去重：同一路径只留第一次出现（文件优先于目录）
    seen: dict[str, Entry] = {}
    for entry in entries:
        current = seen.get(entry.path)
        if current is None or (current.kind == "dir" and entry.kind != "dir"):
            seen[entry.path] = entry
    return sorted(seen.values(), key=lambda e: (e.path.count("/"), e.path))


# ---------------------------------------------------------------- deb


def ar_archive(members: list[tuple[str, bytes]]) -> bytes:
    """写 BSD 风格的 ar 归档（deb 用的就是这个）。"""
    out = bytearray(b"!<arch>\n")
    for name, data in members:
        header = (
            f"{name:<16}{MTIME:<12}{0:<6}{0:<6}{'100644':<8}{len(data):<10}".encode()
            + b"`\n"
        )
        assert len(header) == 60, len(header)
        out += header + data
        if len(data) % 2:
            out += b"\n"
    return bytes(out)


def tar_bytes(items: list[Entry], *, data_layer: bool) -> bytes:
    """按 deb 的约定打包：data 层路径以 ./ 开头，条目按路径排序。"""
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w", format=tarfile.GNU_FORMAT) as tar:
        for entry in items:
            info = tarfile.TarInfo("." + entry.path + ("/" if entry.kind == "dir" else ""))
            info.uid = info.gid = 0
            info.uname = info.gname = "root"
            info.mtime = MTIME
            if entry.kind == "dir":
                info.type = tarfile.DIRTYPE
                info.mode = 0o755
                tar.addfile(info)
            elif entry.kind == "link":
                info.type = tarfile.SYMTYPE
                info.linkname = entry.link
                info.mode = 0o777
                tar.addfile(info)
            else:
                info.type = tarfile.REGTYPE
                info.mode = entry.mode
                info.size = len(entry.data)
                tar.addfile(info, io.BytesIO(entry.data))
    return buffer.getvalue()


def build_deb(entries: list[Entry], ver: str, release: int) -> Path:
    files = [e for e in entries if e.kind != "dir"]
    installed_kb = max(1, sum(e.size for e in files) // 1024)

    control = (
        f"Package: {PKG_NAME}\n"
        f"Version: {ver}-{release}\n"
        f"Architecture: all\n"
        f"Maintainer: {MAINTAINER}\n"
        f"Installed-Size: {installed_kb}\n"
        f"Depends: python3 (>= 3.8)\n"
        f"Recommends: ffmpeg | gstreamer1.0-tools\n"
        f"Section: {SECTION}\n"
        f"Priority: optional\n"
        + (f"Homepage: {URL}\n" if URL else "")
        + f"Description: {SUMMARY}\n"
        + "".join(f" {line}\n" if line.strip() else " .\n"
                  for line in DESCRIPTION.strip().splitlines())
    )

    md5sums = "".join(
        f"{e.digest}  {e.path.lstrip('/')}\n" for e in files if e.kind == "file"
    )

    control_tar = io.BytesIO()
    with tarfile.open(fileobj=control_tar, mode="w", format=tarfile.GNU_FORMAT) as tar:
        for name, payload in (("./control", control.encode()), ("./md5sums", md5sums.encode())):
            info = tarfile.TarInfo(name)
            info.uid = info.gid = 0
            info.uname = info.gname = "root"
            info.mtime = MTIME
            info.mode = 0o644
            info.size = len(payload)
            tar.addfile(info, io.BytesIO(payload))

    data_tar = tar_bytes(entries, data_layer=True)
    out = DIST / f"{PKG_NAME}_{ver}-{release}_all.deb"
    DIST.mkdir(exist_ok=True)
    out.write_bytes(ar_archive([
        ("debian-binary", b"2.0\n"),
        ("control.tar.gz", gzip.compress(control_tar.getvalue(), 9, mtime=0)),
        ("data.tar.xz", lzma.compress(data_tar, preset=9)),
    ]))
    return out


# ---------------------------------------------------------------- rpm

RPM_INT32, RPM_INT16, RPM_STRING, RPM_BIN, RPM_STRING_ARRAY, RPM_I18N = 4, 3, 6, 7, 8, 9

TAG_HEADERI18NTABLE = 100
TAG_NAME, TAG_VERSION, TAG_RELEASE = 1000, 1001, 1002
TAG_SUMMARY, TAG_DESCRIPTION, TAG_BUILDTIME, TAG_BUILDHOST = 1004, 1005, 1006, 1007
TAG_SIZE, TAG_LICENSE, TAG_PACKAGER, TAG_GROUP, TAG_URL = 1009, 1014, 1015, 1016, 1020
TAG_OS, TAG_ARCH = 1021, 1022
TAG_FILESIZES, TAG_FILEMODES, TAG_FILERDEVS, TAG_FILEMTIMES = 1028, 1030, 1033, 1034
TAG_FILEDIGESTS, TAG_FILELINKTOS, TAG_FILEFLAGS = 1035, 1036, 1037
TAG_FILEUSERNAME, TAG_FILEGROUPNAME, TAG_SOURCERPM = 1039, 1040, 1044
TAG_FILEVERIFYFLAGS, TAG_ARCHIVESIZE = 1045, 1046
TAG_DIRINDEXES, TAG_BASENAMES, TAG_DIRNAMES = 1116, 1117, 1118
TAG_PROVIDENAME, TAG_PROVIDEFLAGS, TAG_PROVIDEVERSION = 1047, 1112, 1113
TAG_REQUIREFLAGS, TAG_REQUIRENAME, TAG_REQUIREVERSION = 1048, 1049, 1050
TAG_RPMVERSION, TAG_PAYLOADFORMAT, TAG_PAYLOADCOMPRESSOR, TAG_PAYLOADFLAGS = 1064, 1124, 1125, 1126
TAG_FILEDIGESTALGO = 5011
TAG_ENCODING = 5062
TAG_PAYLOADDIGEST, TAG_PAYLOADDIGESTALGO = 5092, 5093

RPMSENSE_LESS, RPMSENSE_GREATER, RPMSENSE_EQUAL = 2, 4, 8
DIGEST_MD5 = 1
DIGEST_SHA256 = 8


def _pack_values(typ: int, values) -> tuple[bytes, int]:
    if typ == RPM_INT32:
        return struct.pack(f">{len(values)}I", *values), len(values)
    if typ == RPM_INT16:
        return struct.pack(f">{len(values)}H", *values), len(values)
    if typ == RPM_STRING:
        return values.encode() + b"\0", 1
    if typ in (RPM_STRING_ARRAY, RPM_I18N):
        return b"".join(v.encode() + b"\0" for v in values), len(values)
    if typ == RPM_BIN:
        return values, len(values)
    raise ValueError(f"未知类型 {typ}")


def rpm_header(items: list[tuple[int, int, object]], region_tag: int | None = None) -> bytes:
    """items: (tag, type, value)，会按 tag 升序写入并做对齐。

    region_tag 是 rpm 的「区域标签」：签名头用 62（HEADERSIGNATURES），
    主头用 63（HEADERIMMUTABLE）。数据区末尾要多写 16 字节 trailer
    （`{tag, BIN, -(16*il), 16}`），索引第 0 项指回它。少了这一层，rpm 会按
    老式自由格式解析，然后报 "invalid signature tag ... (1046)" 这类错误。
    """
    index = []
    store = bytearray()
    for tag, typ, values in sorted(items, key=lambda item: item[0]):
        alignment = {RPM_INT16: 2, RPM_INT32: 4}[typ] if typ in (RPM_INT16, RPM_INT32) else 1
        while len(store) % alignment:
            store += b"\0"
        offset = len(store)
        payload, count = _pack_values(typ, values)
        store += payload
        index.append((tag, typ, offset, count))

    if region_tag is not None:
        while len(store) % 4:
            store += b"\0"
        trailer_offset = len(store)
        entry_count = len(index) + 1
        # trailer: tag, type=BIN, offset=-(16*entry_count), count=16
        store += struct.pack(">IiiI", region_tag, 7, -(16 * entry_count), 16)
        index.insert(0, (region_tag, 7, trailer_offset, 16))

    head = bytearray(b"\x8e\xad\xe8\x01" + b"\0" * 4)
    head += struct.pack(">II", len(index), len(store))
    for tag, typ, offset, count in index:
        head += struct.pack(">IIII", tag, typ, offset, count)
    return bytes(head) + bytes(store)


def cpio_newc(entries: list[Entry]) -> bytes:
    """新版 cpio（070701）——rpm 载荷就是这个。"""
    out = bytearray()
    inode = 1024

    def add(name: str, mode: int, payload: bytes, nlink: int) -> None:
        nonlocal inode
        raw_name = name.encode() + b"\0"
        out.extend(b"070701")
        out.extend(b"%08X" % inode)
        out.extend(b"%08X" % mode)
        out.extend(b"%08X" % 0)          # uid
        out.extend(b"%08X" % 0)          # gid
        out.extend(b"%08X" % nlink)
        out.extend(b"%08X" % MTIME)
        out.extend(b"%08X" % len(payload))
        out.extend(b"%08X" % 0)          # devmajor
        out.extend(b"%08X" % 0)          # devminor
        out.extend(b"%08X" % 0)          # rdevmajor
        out.extend(b"%08X" % 0)          # rdevminor
        out.extend(b"%08X" % len(raw_name))
        out.extend(b"%08X" % 0)          # check
        out.extend(raw_name)
        while len(out) % 4:
            out.extend(b"\0")
        out.extend(payload)
        while len(out) % 4:
            out.extend(b"\0")
        inode += 1

    for entry in entries:
        name = "." + entry.path
        if entry.kind == "dir":
            add(name, 0o040755, b"", 2)
        elif entry.kind == "link":
            add(name, 0o120777, entry.link.encode(), 1)
        else:
            add(name, 0o100000 | entry.mode, entry.data, 1)

    # 结尾标记
    add("TRAILER!!!", 0, b"", 1)
    return bytes(out)


def build_rpm(entries: list[Entry], ver: str, release: int) -> Path:
    files = [e for e in entries if e.kind != "dir"]
    dirs = [e for e in entries if e.kind == "dir"]
    ordered = dirs + files          # cpio 里目录先出现，跟 rpmbuild 一致

    payload = lzma.compress(cpio_newc(ordered), preset=6)
    file_meta = [e for e in ordered]

    # 现代 rpm 用「目录表 + 基名表 + 目录索引」描述文件列表
    dirnames: list[str] = []
    lookup: dict[str, int] = {}
    dirindexes: list[int] = []
    basenames: list[str] = []
    for entry in file_meta:
        head, _, base = entry.path.rpartition("/")
        directory = head + "/"
        if directory not in lookup:
            lookup[directory] = len(dirnames)
            dirnames.append(directory)
        dirindexes.append(lookup[directory])
        basenames.append(base)

    main_items: list[tuple[int, int, object]] = [
        (TAG_HEADERI18NTABLE, RPM_STRING, "C"),
        (TAG_NAME, RPM_STRING, PKG_NAME),
        (TAG_VERSION, RPM_STRING, ver),
        (TAG_RELEASE, RPM_STRING, str(release)),
        (TAG_SUMMARY, RPM_I18N, [SUMMARY]),
        (TAG_DESCRIPTION, RPM_I18N, [DESCRIPTION.strip()]),
        (TAG_BUILDTIME, RPM_INT32, [MTIME]),
        (TAG_BUILDHOST, RPM_STRING, "localhost"),
        (TAG_SIZE, RPM_INT32, [sum(e.size for e in files)]),
        (TAG_LICENSE, RPM_STRING, LICENSE),
        (TAG_PACKAGER, RPM_STRING, MAINTAINER),
        (TAG_GROUP, RPM_I18N, [GROUP]),
        (TAG_OS, RPM_STRING, "linux"),
        (TAG_ARCH, RPM_STRING, "noarch"),
        (TAG_SOURCERPM, RPM_STRING, f"{PKG_NAME}-{ver}-{release}.src.rpm"),
        (TAG_FILESIZES, RPM_INT32, [e.size for e in file_meta]),
        (TAG_DIRINDEXES, RPM_INT32, dirindexes),
        (TAG_BASENAMES, RPM_STRING_ARRAY, basenames),
        (TAG_DIRNAMES, RPM_STRING_ARRAY, dirnames),
        (TAG_FILEMODES, RPM_INT16, [e.mode | (0o040000 if e.kind == "dir" else
                                             0o120000 if e.kind == "link" else 0o100000)
                                    for e in file_meta]),
        (TAG_FILERDEVS, RPM_INT16, [0] * len(file_meta)),
        (TAG_FILEMTIMES, RPM_INT32, [MTIME] * len(file_meta)),
        (TAG_FILEDIGESTS, RPM_STRING_ARRAY, [e.digest for e in file_meta]),
        (TAG_FILELINKTOS, RPM_STRING_ARRAY, [e.link for e in file_meta]),
        (TAG_FILEFLAGS, RPM_INT32, [0] * len(file_meta)),
        (TAG_FILEUSERNAME, RPM_STRING_ARRAY, ["root"] * len(file_meta)),
        (TAG_FILEGROUPNAME, RPM_STRING_ARRAY, ["root"] * len(file_meta)),
        (TAG_FILEVERIFYFLAGS, RPM_INT32, [0xFFFF_FFFF] * len(file_meta)),
        (TAG_PROVIDENAME, RPM_STRING_ARRAY, [PKG_NAME]),
        (TAG_PROVIDEFLAGS, RPM_INT32, [RPMSENSE_EQUAL]),
        (TAG_PROVIDEVERSION, RPM_STRING_ARRAY, [f"{ver}-{release}"]),
        (TAG_REQUIRENAME, RPM_STRING_ARRAY, ["python3"]),
        (TAG_REQUIREFLAGS, RPM_INT32, [RPMSENSE_GREATER | RPMSENSE_EQUAL]),
        (TAG_REQUIREVERSION, RPM_STRING_ARRAY, ["3.8"]),
        (TAG_RPMVERSION, RPM_STRING, "4.14.0"),
        (TAG_ENCODING, RPM_STRING, "utf-8"),
        (TAG_PAYLOADFORMAT, RPM_STRING, "cpio"),
        (TAG_PAYLOADCOMPRESSOR, RPM_STRING, "xz"),
        (TAG_PAYLOADFLAGS, RPM_STRING, "2"),
        (TAG_FILEDIGESTALGO, RPM_INT32, [DIGEST_MD5] * len(file_meta)),
        (TAG_PAYLOADDIGEST, RPM_STRING_ARRAY, [hashlib.sha256(payload).hexdigest()]),
        (TAG_PAYLOADDIGESTALGO, RPM_INT32, [DIGEST_SHA256]),
    ]
    if URL:
        main_items.append((TAG_URL, RPM_STRING, URL))
    header = rpm_header(main_items, region_tag=63)      # HEADERIMMUTABLE
    body = header + payload

    signature = rpm_header([
        (1000, RPM_INT32, [len(body)]),                  # RPMSIGTAG_SIZE
        (1004, RPM_BIN, hashlib.md5(body).digest()),     # RPMSIGTAG_MD5
        (269, RPM_STRING, hashlib.sha1(body).hexdigest()),
        (273, RPM_STRING, hashlib.sha256(body).hexdigest()),
        (1007, RPM_INT32, [len(payload)]),               # RPMSIGTAG_PAYLOADSIZE
    ], region_tag=62)                                        # HEADERSIGNATURES
    while (len(signature) + 96) % 8:
        signature += b"\0"

    lead = bytearray()
    lead += b"\xed\xab\xee\xdb"          # magic
    lead += bytes([3, 0])                # 版本 3.0
    lead += struct.pack(">h", 0)         # 类型：二进制
    lead += struct.pack(">h", 1)         # archnum（x86 系固定 1，真实架构在头里）
    lead += f"{PKG_NAME}-{ver}-{release}".encode()[:66].ljust(66, b"\0")
    lead += struct.pack(">h", 1)         # osnum: Linux
    lead += struct.pack(">h", 5)         # 签名类型：header 风格
    lead += b"\0" * 16                   # 保留

    out = DIST / f"{PKG_NAME}-{ver}-{release}.noarch.rpm"
    DIST.mkdir(exist_ok=True)
    out.write_bytes(bytes(lead) + signature + body)
    return out


# ---------------------------------------------------------------- 自检


def verify_deb(path: Path, entries: list[Entry]) -> None:
    raw = path.read_bytes()
    assert raw[:8] == b"!<arch>\n", "不是 ar 归档"
    offset, members = 8, []
    while offset < len(raw):
        header = raw[offset:offset + 60]
        name = header[:16].decode().strip()
        size = int(header[48:58].decode().strip())
        body = raw[offset + 60:offset + 60 + size]
        members.append((name, body))
        offset += 60 + size + (size % 2)
    names = [m[0] for m in members]
    assert names == ["debian-binary", "control.tar.gz", "data.tar.xz"], names
    assert dict(members)["debian-binary"] == b"2.0\n"

    control_tar = tarfile.open(fileobj=io.BytesIO(dict(members)["control.tar.gz"]))
    control = control_tar.extractfile("./control").read().decode()
    assert f"Package: {PKG_NAME}" in control
    assert "Depends: python3 (>= 3.8)" in control

    data_tar = tarfile.open(fileobj=io.BytesIO(dict(members)["data.tar.xz"]))
    packaged = {n.lstrip("./") for n in data_tar.getnames()}
    for entry in entries:
        assert entry.path.lstrip("/") in packaged, f"deb 里缺 {entry.path}"
    print(f"  ✓ deb 自检通过：{len(members)} 个成员，{len(entries)} 个条目，control 字段正常")


def verify_rpm(path: Path, entries: list[Entry]) -> None:
    raw = path.read_bytes()
    assert raw[:4] == b"\xed\xab\xee\xdb", "lead magic 不对"
    assert len(raw) > 96, "文件太短"

    def read_header(offset: int, region_tag: int) -> tuple[dict[int, tuple[int, object]], int]:
        assert raw[offset:offset + 4] == b"\x8e\xad\xe8\x01", "头部 magic 不对"
        count, size = struct.unpack(">II", raw[offset + 8:offset + 16])
        store = offset + 16 + 16 * count

        # 索引第 0 项必须是 region 标签（签名头 62 / 主头 63），指向数据区末尾的 trailer
        tag0, type0, off0, cnt0 = struct.unpack(">IIII", raw[offset + 16:offset + 32])
        assert (tag0, type0, cnt0) == (region_tag, 7, 16), \
            f"缺 region 标签：拿到 tag={tag0} type={type0} count={cnt0}"
        assert off0 == size - 16, f"region 偏移不对：{off0} != {size - 16}"
        t_tag, t_type, t_off, t_cnt = struct.unpack(">IiiI", raw[store + size - 16:store + size])
        assert (t_tag, t_type, t_cnt) == (region_tag, 7, 16), "trailer 内容不对"
        assert t_off == -(16 * count), f"trailer 偏移不对：{t_off} != {-16 * count}"

        entries: dict[int, tuple[int, object]] = {}
        for i in range(1, count):          # 第 0 项是 region 标签，跳过
            tag, typ, data_offset, n = struct.unpack(">IIII", raw[offset + 16 + 16 * i:offset + 32 + 16 * i])
            chunk = raw[store + data_offset:store + size]
            if typ == RPM_STRING:
                value = chunk.split(b"\0")[0].decode()
            elif typ in (RPM_STRING_ARRAY, RPM_I18N):
                value = [p.decode() for p in chunk.split(b"\0")[:n]]
            elif typ == RPM_INT32:
                value = list(struct.unpack(f">{n}I", chunk[:4 * n]))
            elif typ == RPM_INT16:
                value = list(struct.unpack(f">{n}H", chunk[:2 * n]))
            else:
                value = chunk[:n]
            entries[tag] = (typ, value)
        return entries, store + size

    signature, after_sig = read_header(96, 62)
    assert signature[1004][0] == RPM_BIN, "签名头缺 MD5"
    after_sig = (after_sig + 7) & ~7          # 签名头按 8 字节对齐，主头从这里开始
    main, payload_start = read_header(after_sig, 63)
    payload = raw[payload_start:]

    assert main[TAG_NAME][1] == PKG_NAME
    assert main[TAG_ARCH][1] == "noarch"
    assert main[TAG_PAYLOADFORMAT][1] == "cpio"
    assert main[TAG_PAYLOADCOMPRESSOR][1] == "xz"
    body = raw[after_sig:]
    assert signature[1004][1] == hashlib.md5(body).digest(), "MD5 不匹配"
    assert signature[269][1] == hashlib.sha1(body).hexdigest(), "SHA1 不匹配"
    assert main[TAG_PAYLOADDIGEST][1][0] == hashlib.sha256(payload).hexdigest(), "载荷摘要不匹配"

    unpacked = lzma.decompress(payload)
    assert b"TRAILER!!!" in unpacked, "cpio 缺结尾标记"
    names = re.findall(rb"070701.{104}((?:[^\0])+)\0", unpacked, re.S)
    names = [n.decode() for n in names]
    assert any(n.endswith("/usr/bin/mj") for n in names), names[:5]

    # 文件列表（目录表 + 基名表 + 索引）必须和载荷、和我们提供的清单三方一致
    dirnames = main[TAG_DIRNAMES][1]
    basenames = main[TAG_BASENAMES][1]
    dirindexes = main[TAG_DIRINDEXES][1]
    listed = {dirnames[i] + base for i, base in zip(dirindexes, basenames)}
    expected = {entry.path for entry in entries}
    assert listed == expected, f"文件列表不一致：多 {listed - expected} 少 {expected - listed}"
    payload_paths = {n[1:] for n in names if not n.endswith("TRAILER!!!")}
    assert payload_paths == expected, "载荷里的路径与清单不一致"

    sizes = main[TAG_FILESIZES][1]
    print(f"  ✓ rpm 自检通过：{len(sizes)} 个条目、{len(names) - 1} 个 cpio 文件、"
          f"文件列表与载荷一致、校验和匹配")


# ---------------------------------------------------------------- 入口


def main() -> int:
    parser = argparse.ArgumentParser(description="打包 mj-cli 为 deb / rpm")
    parser.add_argument("--deb", action="store_true", help="只打 deb")
    parser.add_argument("--rpm", action="store_true", help="只打 rpm")
    parser.add_argument("--verify", action="store_true", help="打完后自检")
    args = parser.parse_args()
    both = not (args.deb or args.rpm)

    ver, release = version()
    entries = collect(ver)
    total = sum(e.size for e in entries if e.kind == "file")
    print(f"{PKG_NAME} {ver}-{release}：{len(entries)} 个条目，展开 {total / 1024 / 1024:.1f}MB")

    built: list[tuple[Path, str]] = []
    if both or args.deb:
        path = build_deb(entries, ver, release)
        built.append((path, "deb"))
        print(f"  → {path.relative_to(ROOT)}（{path.stat().st_size / 1024 / 1024:.1f}MB）")
    if both or args.rpm:
        path = build_rpm(entries, ver, release)
        built.append((path, "rpm"))
        print(f"  → {path.relative_to(ROOT)}（{path.stat().st_size / 1024 / 1024:.1f}MB）")

    if args.verify:
        for path, kind in built:
            if kind == "deb":
                verify_deb(path, entries)
            else:
                verify_rpm(path, entries)
    return 0


if __name__ == "__main__":
    sys.exit(main())
