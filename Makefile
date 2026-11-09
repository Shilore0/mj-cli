PY ?= python3

.PHONY: help test assets package deb rpm smoke install uninstall clean

help:
	@echo "make test     跑单元测试"
	@echo "make assets   重建素材（需要 ffmpeg）"
	@echo "make package  打 deb + rpm 并自检"
	@echo "make smoke    在 Linux 上安装→校验→卸载（需要 sudo）"
	@echo "make install  软链到 ~/.local/bin"
	@echo "make clean    清理构建产物与缓存"

test:
	$(PY) -m unittest discover -s tests -v

assets:
	$(PY) scripts/build_assets.py

package:
	$(PY) packaging/build_packages.py --verify

deb:
	$(PY) packaging/build_packages.py --deb --verify

rpm:
	$(PY) packaging/build_packages.py --rpm --verify

smoke:
	bash packaging/smoke-test.sh

install:
	./install.sh

uninstall:
	./uninstall.sh

clean:
	rm -rf dist build *.egg-info _tmp _pkgcheck _install_test
	find . -name "__pycache__" -type d -prune -exec rm -rf {} +
