"""1. 読み込み：Amazon セラーセントラルの日次トランザクション CSV を探して読む

セラーセントラル「支払い → レポートリポジトリ」で、開始日＝終了日にしてダウンロードした
「2026Oct15-2026Oct15CustomUnifiedTransaction.csv」のようなファイルが対象。
同じ日を2回ダウンロードした「… (1).csv」は1つにまとめる。
"""

import csv
import re
from datetime import date
from pathlib import Path

MONTHS = {m: i for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], start=1)}
# 例: 2026Oct15-2026Oct15CustomUnifiedTransaction.csv / 2026Sep8-2026Sep8CustomUnifiedTransaction (1).csv
FILE_PATTERN = re.compile(r"^(\d{4})([A-Z][a-z]{2})(\d{1,2})-(\d{4})([A-Z][a-z]{2})(\d{1,2})CustomUnifiedTransaction( \(\d+\))?\.csv$")


def date_of(path):
    """ファイル名から日付を取り出す。1日分（開始日＝終了日）のファイルでなければ None"""
    m = FILE_PATTERN.match(Path(path).name)
    if not m or m.group(2) not in MONTHS or m.group(5) not in MONTHS:
        return None
    start = date(int(m.group(1)), MONTHS[m.group(2)], int(m.group(3)))
    end = date(int(m.group(4)), MONTHS[m.group(5)], int(m.group(6)))
    return start if start == end else None


def find_reports(folder, date_from=None, date_to=None):
    """フォルダから日次 CSV を探して {日付: パス} を返す。同じ日が複数あれば「(1)」の付かない方を使う"""
    found = {}
    for path in sorted(Path(folder).glob("*CustomUnifiedTransaction*.csv")):
        day = date_of(path)
        if day is None:
            continue
        if (date_from and day < date_from) or (date_to and day > date_to):
            continue
        is_copy = "(" in path.name
        if day not in found or (found[day][1] and not is_copy):
            found[day] = (path, is_copy)
    return {day: p for day, (p, _) in sorted(found.items())}


def read_transactions(path):
    """CSV の明細行を dict のリストで返す（先頭の説明行は飛ばし、"date/time" で始まる見出し行から読む）"""
    with open(path, encoding="utf-8-sig", newline="") as f:
        lines = f.read().splitlines()
    for i, line in enumerate(lines):
        if line.startswith('"date/time",'):
            return list(csv.DictReader(lines[i:]))
    return []   # その日の取引が無いと見出し行も無いことがある
