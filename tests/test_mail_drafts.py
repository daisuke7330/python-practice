"""mail_drafts の単体テスト（Outlook には接続しない）

実行: python -m unittest tests.test_mail_drafts -v
"""

import os
import tempfile
import time
import unittest
from datetime import date
from pathlib import Path

from mail_drafts.attachments import latest_file
from mail_drafts.template import fill, load_templates, render
from mail_drafts.week import next_monday, week_of_month, week_values

BASE_DIR = Path(__file__).resolve().parent.parent


class WeekTest(unittest.TestCase):
    def test_next_monday(self):
        self.assertEqual(next_monday(date(2026, 10, 29)), date(2026, 11, 2))   # 木曜 → 翌週の月曜
        self.assertEqual(next_monday(date(2026, 10, 26)), date(2026, 11, 2))   # 月曜でも1週間後

    def test_week_of_month(self):
        self.assertEqual(week_of_month(date(2026, 11, 2)), 1)
        self.assertEqual(week_of_month(date(2026, 11, 9)), 2)
        self.assertEqual(week_of_month(date(2026, 11, 30)), 5)

    def test_week_values_cross_month(self):
        v = week_values(date(2026, 10, 29))
        self.assertEqual((v["month"], v["week"], v["from"], v["to"]), (11, 1, "11/2", "11/8"))


class TemplateTest(unittest.TestCase):
    def test_fill_keeps_unknown(self):
        self.assertEqual(fill("{month}月 {nai}", {"month": 11}), "11月 {nai}")

    def test_render_with_and_without_extra(self):
        tpl = {"subject": "{month}月第{week}週", "body": "皆様\n\n本文\n{extra}\n\nよろしく\n\n{sign}", "sign": "署名", "to": ["a@example.com"]}
        m = render(tpl, {"month": 11, "week": 1})
        self.assertEqual(m["subject"], "11月第1週")
        self.assertNotIn("\n\n\n", m["body"]); self.assertTrue(m["body"].endswith("署名")); self.assertEqual(m["unfilled"], [])
        m2 = render(tpl, {"month": 11, "week": 1}, "黄色は新商品です")
        self.assertIn("本文\n黄色は新商品です\n", m2["body"])

    def test_render_reports_unfilled(self):
        m = render({"subject": "{nazo}", "body": "x"}, {})
        self.assertEqual(m["unfilled"], ["{nazo}"])

    def test_sample_templates_load(self):
        t = load_templates(BASE_DIR / "mail_templates.sample.json")
        self.assertIn("媒体掲載予定", t); self.assertNotIn("_説明", t)


class AttachmentTest(unittest.TestCase):
    def test_latest_file(self):
        with tempfile.TemporaryDirectory() as d:
            old = Path(d) / "掲載予定_20261024.xlsx"; new = Path(d) / "掲載予定_20261030.xlsx"
            lock = Path(d) / "~$掲載予定_20261031.xlsx"
            for p in (old, new, lock):
                p.write_text("x")
            now = time.time(); os.utime(old, (now - 100, now - 100)); os.utime(new, (now, now)); os.utime(lock, (now + 10, now + 10))
            self.assertEqual(latest_file(d, "掲載予定_*.xlsx"), new)   # 開いている時の一時ファイル（~$）は除く
            self.assertIsNone(latest_file(d, "*.zip"))


if __name__ == "__main__":
    unittest.main()
