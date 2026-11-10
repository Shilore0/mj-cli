"""mj 的核心逻辑测试：抽签概率、尺寸档位、预渲染帧包、渲染器。

跑法：python3 -m unittest discover -s tests -v
（需要先构建素材：python3 scripts/build_assets.py）
"""

from __future__ import annotations

import random
import re
import sys
import unittest
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from mj import manifest, render_cells, term  # noqa: E402
from mj.paths import assets_dir  # noqa: E402

BASE = assets_dir()
DATA = manifest.load(BASE)
EFFECTS = manifest.effects(DATA)
ANSI = re.compile(r"\x1b\[[0-9;]*m")


class TestManifest(unittest.TestCase):
    def test_has_two_effects(self):
        self.assertEqual([e["id"] for e in EFFECTS], ["hang", "pose"])
        self.assertEqual([e["label"] for e in EFFECTS], ["倒挂", "耍帅"])

    def test_every_effect_has_assets(self):
        for effect in EFFECTS:
            with self.subTest(effect=effect["id"]):
                self.assertTrue((BASE / effect["wav"]).exists(), effect["wav"])
                self.assertTrue((BASE / effect["webm"]).exists(), effect["webm"])
                themes = effect["cache"]["themes"]
                self.assertIn("dark", themes)
                self.assertIn("light", themes)
                self.assertGreaterEqual(len(themes["dark"]["buckets"]), 3)


class TestPick(unittest.TestCase):
    def test_distribution_is_about_half(self):
        rng = random.Random(20260801)
        counts = {"hang": 0, "pose": 0}
        for _ in range(4000):
            counts[manifest.pick(EFFECTS, rng=rng)["id"]] += 1
        self.assertGreater(counts["hang"], 1800)
        self.assertLess(counts["hang"], 2200)
        self.assertEqual(sum(counts.values()), 4000)

    def test_consecutive_repeats_allowed(self):
        """不做「避免连击」，连续两次抽到同一个是合法结果。"""
        rng = random.Random(7)
        picks = [manifest.pick(EFFECTS, rng=rng)["id"] for _ in range(40)]
        self.assertTrue(any(a == b for a, b in zip(picks, picks[1:])))

    def test_forced_pick(self):
        self.assertEqual(manifest.pick(EFFECTS, forced="hang")["id"], "hang")
        self.assertEqual(manifest.pick(EFFECTS, forced="耍帅")["id"], "pose")
        with self.assertRaises(manifest.AssetError):
            manifest.pick(EFFECTS, forced="不给")


class TestChoose(unittest.TestCase):
    def setUp(self):
        self.stages = {}
        for effect in EFFECTS:
            entry, blob = manifest.load_terminal(BASE, effect["id"])
            self.stages[effect["id"]] = term.TerminalStage(entry, blob)

    def test_bucket_fits_terminal(self):
        for eid, stage in self.stages.items():
            for cols, rows in [(80, 24), (120, 40), (200, 60), (40, 12)]:
                spot = stage.choose(cols, rows, align="center")
                bucket = spot["bucket"]
                with self.subTest(effect=eid, term=f"{cols}x{rows}"):
                    self.assertLessEqual(bucket["width"], cols)
                    self.assertLessEqual(spot["rows"], max(1, rows - 1))
                    self.assertGreaterEqual(spot["col"], 1)
                    self.assertGreaterEqual(spot["row"], 1)

    def test_bigger_terminal_gets_bigger_sprite(self):
        stage = self.stages["pose"]
        small = stage.choose(80, 24)["bucket"]["width"]
        large = stage.choose(200, 60)["bucket"]["width"]
        self.assertGreater(large, small)

    def test_size_cap(self):
        stage = self.stages["pose"]
        spot = stage.choose(200, 60, width=26)
        self.assertLessEqual(spot["bucket"]["width"], 26)

    def test_hang_is_top_aligned(self):
        stage = self.stages["hang"]
        self.assertEqual(stage.choose(120, 40, align="top")["row"], 1)

    def test_tiny_terminal_still_renders(self):
        stage = self.stages["hang"]
        spot = stage.choose(20, 6)
        self.assertEqual(spot["rows"], 5)


class TestPacks(unittest.TestCase):
    def test_frames_match_bucket_geometry(self):
        for effect in EFFECTS:
            entry, blob = manifest.load_terminal(BASE, effect["id"])
            for bucket in entry["buckets"]:
                for frame_no in (0, entry["count"] // 2, entry["count"] - 1):
                    offset = bucket["offsets"][frame_no]
                    raw = zlib.decompress(blob[offset:offset + bucket["lengths"][frame_no]])
                    lines = raw.decode("utf-8").split("\n")
                    with self.subTest(effect=effect["id"], bucket=bucket["width"], frame=frame_no):
                        self.assertEqual(len(lines), bucket["rows"])
                        self.assertEqual(len(ANSI.sub("", lines[0])), bucket["width"])

    def test_light_theme_is_prebuilt(self):
        entry, blob = manifest.load_terminal(BASE, "pose", theme="light")
        bucket = entry["buckets"][0]
        light = zlib.decompress(blob[bucket["offsets"][0]:][:bucket["lengths"][0]])
        self.assertIsInstance(light, bytes)

    def test_first_frame_blank_middle_frame_colored(self):
        entry, blob = manifest.load_terminal(BASE, "pose")
        bucket = max(entry["buckets"], key=lambda b: b["width"])

        def lines_of(frame_no):
            offset = bucket["offsets"][frame_no]
            text = zlib.decompress(blob[offset:offset + bucket["lengths"][frame_no]])
            return text.decode("utf-8").split("\n")

        for line in lines_of(0):
            self.assertEqual(ANSI.sub("", line).strip(), "")
        middle = "\n".join(lines_of(45))
        self.assertIn("38;2;", middle)


class TestAudioRules(unittest.TestCase):
    """声音跟调用名的大小写走：小写 mj 静音，大写 MJ 带音乐。"""

    def test_lowercase_is_silent(self):
        from mj.cli import audio_by_default, resolve_audio

        self.assertFalse(audio_by_default("mj"))
        enabled, _ = resolve_audio(False, False, "mj")
        self.assertFalse(enabled)

    def test_uppercase_has_music(self):
        from mj.cli import audio_by_default, resolve_audio

        self.assertTrue(audio_by_default("MJ"))
        enabled, reason = resolve_audio(False, False, "MJ")
        self.assertTrue(enabled)
        self.assertIn("大写", reason)

    def test_explicit_flags_win(self):
        from mj.cli import resolve_audio

        self.assertTrue(resolve_audio(True, False, "mj")[0])    # mj --audio
        self.assertFalse(resolve_audio(False, True, "MJ")[0])   # MJ --no-audio
        self.assertFalse(resolve_audio(True, True, "MJ")[0])    # 两个都给时静音优先

    def test_other_invocations_are_silent(self):
        from mj.cli import audio_by_default

        for name in ("__main__.py", "mj.py", "python3", "", "Mz"):
            with self.subTest(name=name):
                self.assertFalse(audio_by_default(name))


class TestRenderCells(unittest.TestCase):
    """构建期渲染器：透明帧必须全留空，且每行宽度严格等于桶宽。"""

    def test_render_rows_blank_frame(self):
        plan = render_cells.sampler(8, 12, 8, 12)
        frame = bytes(8 * 12 * 4)  # 全透明
        lines = render_cells.render_rows(frame, plan, 8)
        self.assertEqual(len(lines), 6)
        for line in lines:
            self.assertEqual(len(ANSI.sub("", line)), 8)
            self.assertNotIn("38;2;", line)

    def test_render_rows_opaque_frame(self):
        plan = render_cells.sampler(4, 4, 4, 4)
        frame = bytes([255, 0, 0, 255]) * 16
        lines = render_cells.render_rows(frame, plan, 4)
        self.assertEqual(len(lines), 2)
        self.assertIn("38;2;255;0;0", lines[0])


if __name__ == "__main__":
    unittest.main()


class TestRpmHeader(unittest.TestCase):
    """rpm 头必须是标准 region 结构，否则 rpm 会报 invalid signature tag。"""

    @classmethod
    def setUpClass(cls):
        # 目录名 packaging 会被 PyPI 的同名库盖住，按路径加载
        import importlib.util
        from pathlib import Path as _P

        path = _P(__file__).resolve().parent.parent / "packaging" / "build_packages.py"
        import sys

        spec = importlib.util.spec_from_file_location("mj_build_packages", path)
        cls.bp = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = cls.bp      # dataclass 需要能在 sys.modules 里找到模块
        spec.loader.exec_module(cls.bp)

    def check(self, region_tag, tag_for_payload):
        import struct

        header = self.bp.rpm_header([(tag_for_payload, self.bp.RPM_STRING, "x")], region_tag=region_tag)
        il, dl = struct.unpack(">II", header[8:16])
        store = 16 + 16 * il

        tag0, type0, off0, count0 = struct.unpack(">IIII", header[16:32])
        self.assertEqual((tag0, type0, count0), (region_tag, 7, 16))
        self.assertEqual(off0, dl - 16, "region 偏移应指向数据区末尾 16 字节")

        t_tag, t_type, t_off, t_count = struct.unpack(">IiiI", header[store + dl - 16:store + dl])
        self.assertEqual((t_tag, t_type, t_count), (region_tag, 7, 16))
        self.assertEqual(t_off, -16 * il, "trailer 里的 -(16*il) 不对")

    def test_signature_region(self):
        self.check(62, 1000)

    def test_main_region(self):
        self.check(63, 1000)



