"""Windows 控制台：打开 ANSI 转义（VT）支持，退出时还原。

Windows Terminal 默认支持转义序列，但传统 conhost（PowerShell 直接开的窗口）
需要显式给 stdout 打上 ENABLE_VIRTUAL_TERMINAL_PROCESSING，否则会看到
`←[38;2;255;0;0m` 这种原始序列。非 Windows 平台这个类是空操作。
"""

from __future__ import annotations

import os
import sys

ENABLE_PROCESSED_OUTPUT = 0x0001
ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004


class VirtualTerminal:
    """用完记得 restore()，否则会把用户后续的输出也改成 VT 模式（其实通常无害）。"""

    def __init__(self, stream=None):
        self.stream = stream or sys.stdout
        self.handle = None
        self.original = None

    def enable(self) -> "VirtualTerminal":
        if os.name != "nt":
            return self
        try:
            import ctypes
            import msvcrt

            handle = msvcrt.get_osfhandle(self.stream.fileno())
            kernel32 = ctypes.windll.kernel32
            mode = ctypes.c_uint32()
            if not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
                return self          # 不是控制台（被重定向了），什么都不用做
            self.handle = handle
            self.original = mode.value
            kernel32.SetConsoleMode(
                handle, mode.value | ENABLE_PROCESSED_OUTPUT | ENABLE_VIRTUAL_TERMINAL_PROCESSING
            )
        except (ImportError, OSError, ValueError, AttributeError):
            self.handle = None
        return self

    def restore(self) -> None:
        if self.handle is None or self.original is None:
            return
        try:
            import ctypes

            ctypes.windll.kernel32.SetConsoleMode(self.handle, self.original)
        except (ImportError, OSError, AttributeError):
            pass
        self.handle = None

    def __enter__(self) -> "VirtualTerminal":
        return self.enable()

    def __exit__(self, *exc_info) -> None:
        self.restore()
