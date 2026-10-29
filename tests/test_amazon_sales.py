"""amazon_sales の単体テスト（Google には接続しない）

実行: python -m unittest tests.test_amazon_sales -v
"""

import tempfile
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path

from amazon_sales.aggregate import daily_sales, monthly_summary
from amazon_sales.csv_reader import date_of, find_reports, read_transactions
from amazon_sales.sheet_writer import merge_daily, rows_to_days

INTRO = '"Includes Amazon Marketplace ..."\n"All amounts in USD, unless specified"\n"date/time: posted date/time of the transaction"\n'
HEAD = '"date/time","settlement id","type","order id","sku","description","quantity","total"\n'
ORDER = '"Oct 15, 2026 9:16:12 PM PDT","1","Order","111-1","SKU","item","1","42.63"\n'
TRANSFER = '"Oct 15, 2026 10:46:27 PM PDT","1","Transfer","","","To your account","","-393.19"\n'
REFUND = '"Oct 15, 2026 11:00:00 PM PDT","1","Refund","111-2","SKU","item","1","-19.66"\n'
FEE = '"Oct 15, 2026 11:30:00 PM PDT","1","Service Fee","","","Subscription","","-39.99"\n'


class CsvReaderTest(unittest.TestCase):
    def test_date_of(self):
        self.assertEqual(date_of("2026Oct15-2026Oct15CustomUnifiedTransaction.csv"), date(2026, 10, 15))
        self.assertEqual(date_of("2026Sep8-2026Sep8CustomUnifiedTransaction (1).csv"), date(2026, 9, 8))
        self.assertIsNone(date_of("2026Oct1-2026Oct31CustomUnifiedTransaction.csv"))   # 1か月分のファイルは対象外
        self.assertIsNone(date_of("memo.csv"))

    def test_find_reports_dedupe_and_range(self):
        with tempfile.TemporaryDirectory() as d:
            for name in ["2026Sep8-2026Sep8CustomUnifiedTransaction (1).csv", "2026Sep8-2026Sep8CustomUnifiedTransaction.csv",
                         "2026Sep9-2026Sep9CustomUnifiedTransaction.csv", "2026Oct1-2026Oct1CustomUnifiedTransaction.csv"]:
                (Path(d) / name).write_text(INTRO, encoding="utf-8")
            found = find_reports(d, date(2026, 9, 1), date(2026, 9, 30))
            self.assertEqual(list(found), [date(2026, 9, 8), date(2026, 9, 9)])
            self.assertNotIn("(1)", found[date(2026, 9, 8)].name)

    def test_read_skips_intro_and_handles_empty(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "a.csv"; p.write_text("﻿" + INTRO + HEAD + ORDER, encoding="utf-8")
            rows = read_transactions(p)
            self.assertEqual(len(rows), 1); self.assertEqual(rows[0]["total"], "42.63")
            empty = Path(d) / "b.csv"; empty.write_text(INTRO, encoding="utf-8")
            self.assertEqual(read_transactions(empty), [])


class AggregateTest(unittest.TestCase):
    def rows(self, *lines):
        import csv, io
        return list(csv.DictReader(io.StringIO(HEAD + "".join(lines))))

    def test_transfer_is_not_sales(self):
        d = daily_sales(self.rows(ORDER, TRANSFER))
        self.assertEqual(d["sales"], Decimal("42.63")); self.assertEqual(d["transfer"], Decimal("-393.19")); self.assertEqual(d["orders"], 1)

    def test_minus_day_is_kept(self):
        d = daily_sales(self.rows(REFUND, FEE))
        self.assertEqual(d["sales"], Decimal("-59.65")); self.assertEqual(d["refunds"], 1); self.assertEqual(d["orders"], 0)

    def test_empty_day_is_zero(self):
        self.assertEqual(daily_sales([])["sales"], Decimal("0"))

    def test_monthly(self):
        days = {date(2026, 9, 30): daily_sales(self.rows(ORDER)), date(2026, 10, 1): daily_sales(self.rows(ORDER)),
                date(2026, 10, 2): daily_sales(self.rows(REFUND))}
        m = monthly_summary(days)
        self.assertEqual(list(m), ["2026-09", "2026-10"])
        self.assertEqual(m["2026-10"]["sales"], Decimal("22.97")); self.assertEqual(m["2026-10"]["plus_days"], 1); self.assertEqual(m["2026-10"]["days"], 2)


class SheetMergeTest(unittest.TestCase):
    def test_merge_overwrites_same_date_and_sorts(self):
        existing = [["2026/10/02", "金", 10, 1, 0, 0], ["2026/10/01", "木", 5, 1, 0, 0]]
        merged, added = merge_daily(existing, [["2026/10/02", "金", 12, 1, 0, 0], ["2026/10/03", "土", -3, 0, 1, 0]])
        self.assertEqual([r[0] for r in merged], ["2026/10/01", "2026/10/02", "2026/10/03"])
        self.assertEqual(merged[1][2], 12); self.assertEqual(added, 1)

    def test_rows_to_days(self):
        days = rows_to_days([["2026/10/02", "金", 12.5, 1, 0, -100]])
        self.assertEqual(days[date(2026, 10, 2)]["sales"], Decimal("12.5"))


class MissingDaysTest(unittest.TestCase):
    def test_missing_days(self):
        from amazon_sales_to_sheet import missing_days
        days = {date(2026, 8, 1): {}, date(2026, 8, 3): {}}
        self.assertEqual(missing_days(days), [date(2026, 8, 2)])
        self.assertEqual(missing_days(days, date(2026, 7, 31), date(2026, 8, 3)), [date(2026, 7, 31), date(2026, 8, 2)])


if __name__ == "__main__":
    unittest.main()
