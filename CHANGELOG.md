# Changelog

格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本号遵循语义化版本。

## [Unreleased]

### 新增

- Windows / PowerShell 支持：`bin/mj.cmd` 启动器，`install.ps1` / `uninstall.ps1`（改用户 PATH）。
- 音效新增 `winsound` 后端：Windows 自带，不需要外部播放器。
- 传统 conhost 自动打开 VT 转义（`mj/win_console.py`），否则会显示原始 ANSI 序列。

### 修复

- Windows 上命令名不区分大小写，启动器改用 `%~0` 读取你实际敲的大小写，
  `MJ` 仍能自动带音乐；被规范化时可用 `--audio` 显式出声。

## [1.0] - 2026-11-09

首个正式版本。

### 新增

- 命令行工具 `mj`：每次运行独立掷硬币，各 50% 概率播放「倒挂」或「耍帅」的透明蜘蛛侠。
- 终端渲染：真彩色半块字符（`▀` / `▄`），透明像素留空，终端底色透出；
  备用屏幕播放，退出或 `Ctrl+C` 自动恢复。
- 预渲染 ANSI 帧包：帧在构建期就渲染并 zlib 压缩，运行期只解压 + 输出（0.07–0.13 ms/帧）。
- 5 档尺寸（18/26/36/50/68 列）× 深色/浅色两套主题，运行时按终端大小自动挑选。
- 声音跟随调用名大小写：`mj` 默认静音，`MJ` 默认带音乐；
  `--audio` / `--no-audio` 可反转，`--explain` 可查看判定理由。
- 音轨与动画一对一绑定，构建期用 PCM 摘要校验，防止素材错配。
- 可选 `--window`：GTK3 + cairo 的逐像素透明桌面悬浮窗，失败自动退回终端。
- 打包：纯 Python 手写的 deb / rpm 打包器（不依赖 dpkg-deb / rpmbuild），
  附打包自检与虚拟机安装自检脚本。
- 素材构建脚本：从 Side-by-Side Alpha 源片重建透明 webm、wav 与 ANSI 帧包。

### 说明

- 依赖 Python ≥ 3.8，无第三方库。
- 素材来源于 [MI-KUNs/CN-TikTok-MJ](https://github.com/MI-KUNs/CN-TikTok-MJ)，
  权属与使用限制见 `THIRD_PARTY_NOTICES.md`。
