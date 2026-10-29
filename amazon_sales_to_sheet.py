"""Amazon の日次売上を CSV から集計して Google スプレッドシートに記録する

使い方:
    python amazon_sales_to_sheet.py [--folder フォルダ] [--from 2026-10-01] [--to 2026-10-31] [--dry-run] [--paste]

毎日手で「CSVを開く → total 列を合計 → Transfer（銀行への振込）を引く → 管理表に入力」していた作業を自動化する。
  1. 読み込み（amazon_sales/csv_reader.py）：ダウンロードフォルダの日次 CSV を日付ごとに探す（重複ダウンロードは1つに）
  2. 集計　　（amazon_sales/aggregate.py）  ：1日の売上＝total の合計−Transfer、月ごとの合計
  3. 書き込み（amazon_sales/sheet_writer.py）：Google スプレッドシートの「日次」「月次」シートに書く
--dry-run は画面に表示するだけでシートには書かない。--paste は管理表に貼り付けやすい「売上だけの列」も表示する。
"""

import argparse
from datetime import date, timedelta
from pathlib import Path

from amazon_sales.aggregate import daily_sales, monthly_summary
from amazon_sales.csv_reader import find_reports, read_transactions

DEFAULT_FOLDER = Path.home() / "Downloads"


def parse_args():
    p = argparse.ArgumentParser(description="Amazon の日次 CSV から売上を集計して Google スプレッドシートに記録する")
    p.add_argument("--folder", default=str(DEFAULT_FOLDER), help="CSV のあるフォルダ（既定：ダウンロード）")
    p.add_argument("--from", dest="date_from", type=date.fromisoformat, help="この日から（例 2026-10-01）")
    p.add_argument("--to", dest="date_to", type=date.fromisoformat, help="この日まで（例 2026-10-31）")
    p.add_argument("--dry-run", action="store_true", help="シートに書かず、集計結果を表示するだけ")
    p.add_argument("--paste", action="store_true", help="管理表に貼り付ける用に、売上だけを1日1行で表示する")
    return p.parse_args()


def missing_days(days, date_from=None, date_to=None):
    """期間の中で CSV が見つからなかった日を返す（期間の指定が無ければ、見つかった最初の日～最後の日）"""
    start, end = date_from or min(days), date_to or max(days)
    return [start + timedelta(n) for n in range((end - start).days + 1) if start + timedelta(n) not in days]


def main():
    args = parse_args()
    reports = find_reports(args.folder, args.date_from, args.date_to)
    if not reports:
        print("対象の CSV が見つかりませんでした。--folder と期間を確認してください。")
        return
    days = {day: daily_sales(read_transactions(path)) for day, path in reports.items()}
    print(f"✓ CSV {len(reports)} 日分を集計しました（{min(days)} ～ {max(days)}）")
    missing = missing_days(days, args.date_from, args.date_to)
    if missing:
        print(f"  ※ CSV が無い日が {len(missing)} 日あります（ダウンロード漏れ？）: " + ", ".join(f"{d:%m/%d}" for d in missing[:10])
              + (" …" if len(missing) > 10 else ""))

    for key, m in monthly_summary(days).items():
        print(f"  {key}  売上 {m['sales']:>10,.2f} USD  注文 {m['orders']:>3}件  返金 {m['refunds']}件  "
              f"売上のあった日 {m['plus_days']}/{m['days']}日")
    if args.paste:
        print("--- 貼り付け用（1日1行・売上 USD）---")
        for day, d in days.items():
            print(f"{day:%Y/%m/%d}\t{d['sales']}")

    if args.dry_run:
        print("（--dry-run のためシートには書き込んでいません）")
        return
    from amazon_sales import sheet_writer   # Google のライブラリは書き込む時だけ読み込む
    service = sheet_writer.get_service()
    sid = sheet_writer.get_spreadsheet_id(service)
    total, added = sheet_writer.write(service, sid, days)
    print(f"✓ スプレッドシートに書き込みました（日次 {total} 日分、うち新しく追加 {added} 日）")
    print(f"  https://docs.google.com/spreadsheets/d/{sid}/edit")


if __name__ == "__main__":
    main()
