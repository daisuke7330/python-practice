"""1. 日付：件名に入れる「○月第○週」を計算する

「来週の商材のご連絡」のように、送る日の翌週（月曜始まり）を対象にする。
第○週は、その週の月曜日がその月の何番目の月曜か（1～7日の月曜＝第1週）。
"""

from datetime import date, timedelta


def next_monday(today):
    """today の翌週の月曜日（today が月曜でも1週間後）"""
    return today + timedelta(days=7 - today.weekday())


def week_of_month(monday):
    return (monday.day - 1) // 7 + 1


def week_values(today):
    """ひな形に差し込む値：{today} {month} {week} {from} {to}（来週の月曜～日曜）"""
    mon = next_monday(today)
    return {"today": f"{today:%m/%d}".lstrip("0"), "month": mon.month, "week": week_of_month(mon),
            "from": f"{mon.month}/{mon.day}", "to": f"{(mon + timedelta(6)).month}/{(mon + timedelta(6)).day}"}
