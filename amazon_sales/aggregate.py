"""2. 集計：1日の売上と、月ごとのまとめを計算する

1日の売上 ＝ その日の明細の total 列の合計 − 種類（type）が Transfer の行の total
（Transfer は売上金を銀行口座へ振り込んだ記録なので、売上ではない）
返金や手数料だけの日はマイナスになるが、そのまま残す。
"""

from collections import OrderedDict
from decimal import Decimal


def to_decimal(text):
    text = (text or "").replace(",", "").strip()
    return Decimal(text) if text else Decimal("0")


def daily_sales(rows):
    """1日分の明細から {sales, orders, refunds, transfer} を返す"""
    sales = Decimal("0"); transfer = Decimal("0"); orders = 0; refunds = 0
    for row in rows:
        total = to_decimal(row.get("total"))
        kind = (row.get("type") or "").strip()
        if kind == "Transfer":
            transfer += total
            continue
        sales += total
        if kind == "Order":
            orders += int(to_decimal(row.get("quantity")) or 1)
        elif kind == "Refund":
            refunds += 1
    return {"sales": sales, "orders": orders, "refunds": refunds, "transfer": transfer}


def monthly_summary(days):
    """{日付: daily_sales の結果} から月ごとの {sales, orders, refunds, days, plus_days} を返す"""
    months = OrderedDict()
    for day, d in sorted(days.items()):
        key = f"{day.year}-{day.month:02d}"
        m = months.setdefault(key, {"sales": Decimal("0"), "orders": 0, "refunds": 0, "days": 0, "plus_days": 0})
        m["sales"] += d["sales"]; m["orders"] += d["orders"]; m["refunds"] += d["refunds"]; m["days"] += 1
        if d["sales"] > 0:
            m["plus_days"] += 1
    return months
