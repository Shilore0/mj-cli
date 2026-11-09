# 参与贡献

## 环境

- Python ≥ 3.8（只用标准库，不需要虚拟环境）
- 想重建素材才需要 ffmpeg（`libvpx-vp9` 支持透明通道）
- 想验证包才需要 dpkg / rpm

```bash
git clone <repo> && cd mj-cli
./install.sh          # 装到 ~/.local/bin（只是软链，改代码立即生效）
```

## 跑测试

```bash
python3 -m unittest discover -s tests -v     # 或 make test
```

测试不需要 ffmpeg，但需要 `assets/` 存在（仓库里已经带了构建产物）。

## 改代码时注意

- **`bin/mj` 不要用 `realpath` 改写 `sys.argv[0]`。** 程序靠「自己被叫什么名字」决定默认静音还是带音乐，软链名 `MJ` 必须保留大小写。
- **终端渲染在构建期做，不在运行期做。** 想改颜色/字符，改 `mj/render_cells.py`，然后重新构建素材；不要往 `mj/term.py` 里加逐像素逻辑——那里只应该是解压和输出。
- **音轨绑定是硬约束。** 换素材后 `scripts/build_assets.py` 会用 PCM 摘要校验 wav 与源片是否一致，不一致会直接失败，不要绕过这个检查。

## 重建素材

```bash
python3 scripts/build_assets.py             # 全量（含 VP9 透明编码，约 10 秒）
python3 scripts/build_assets.py --no-webm   # 只重建 ANSI 帧包和 wav
```

改了 `mj/render_cells.py` 或换源片之后必须重建，否则包里的帧还是旧的。

## 打包

```bash
python3 packaging/build_packages.py --verify   # 打 deb + rpm 并自检
bash packaging/smoke-test.sh                   # 在 Linux 上装一遍、验一遍、卸掉
```

## 提交

- 一次提交做一件事，说明写清「为什么」。
- 改到行为（参数、默认值、输出格式）时，同步更新 `README.md` 与 `CHANGELOG.md`。
- 提交前请确认 `make test` 和 `make package` 都是绿的。
