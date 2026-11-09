# 发布到 GitHub

## 0. 先把「这是谁的仓库」改掉

打包元信息里现在挂的是素材来源的上游仓库，不是你的。发布前改一处：

```bash
# 临时覆盖（不改代码）
MJ_HOMEPAGE=https://github.com/<你>/mj-cli python3 packaging/build_packages.py --verify
```

或者把 `packaging/build_packages.py` 里 `URL` 的默认值改成你的仓库地址，一劳永逸。
README 里的 `<repo>` 占位符也一并替换。

## 1. 建仓库并推上去

```bash
git remote add origin git@github.com:<你>/mj-cli.git
git push -u origin main
git push origin v1.0        # 推 tag 会触发 release workflow
```

本地已经初始化好了：`main` 分支两个提交，`v1.0` 标签指向最新提交。

## 2. 自动发版（推荐）

`.github/workflows/release.yml`：推 `v*` 标签即自动

1. 跑单元测试；
2. 打 deb + rpm 并自检；
3. 校验 tag 与 `mj/__init__.py` 里的 `__version__` 一致（不一致直接失败，防止发错版本）；
4. 建 Release、上传 `dist/*`、自动生成发布说明。

所以发版的完整动作就是：

```bash
# 改版本号
$EDITOR mj/__init__.py            # __version__ = "1.1"
$EDITOR CHANGELOG.md              # 加一节
git commit -am "release: 1.1"
git tag -a v1.1 -m "mj-cli 1.1"
git push origin main --tags
```

约定：**tag 名去掉 `v` 必须等于 `__version__`**（`v1.0` ↔ `1.0`）。

## 3. 手工发版（不想用 Actions）

```bash
MJ_HOMEPAGE=https://github.com/<你>/mj-cli python3 packaging/build_packages.py --verify
# 然后在 GitHub 上新建 Release，把 dist/ 里两个文件拖进去
```

`.gitignore` 已经把 `dist/` 排除，包不进仓库，只作 Release 资产。

## 4. CI 还会做什么

`.github/workflows/ci.yml` 在 push / PR 时：

- 用 Python 3.8 / 3.11 / 3.13 各跑一遍单元测试（包声明支持 3.8，所以最低版本必须绿）；
- 打包并自检，产物作为 artifact 上传；
- 另起一个 job 在真的 Ubuntu 上 `dpkg -i` 安装、跑 `packaging/smoke-test.sh`、再卸掉。

## 5. 发布前自查清单

- [ ] `python3 -m unittest discover -s tests` 全绿
- [ ] `python3 packaging/build_packages.py --verify` 两个包都通过自检
- [ ] `bash packaging/smoke-test.sh` 在虚拟机里全绿（含大小写声音规则）
- [ ] `mj/__init__.py` 的版本号 == `CHANGELOG.md` 最新一节 == tag
- [ ] README 里的 `<repo>` 占位和 `packaging/build_packages.py` 的 `URL` 已换成你的仓库
- [ ] `assets/` 是最后一次改渲染逻辑之后重建的（否则包里的帧是旧的）
- [ ] 第三方素材的权属说明（`THIRD_PARTY_NOTICES.md`）随包发布
