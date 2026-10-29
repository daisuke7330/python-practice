"""3. 書き込み：集計結果を Google スプレッドシートに書く

「日次」シート：日付・売上(USD)・注文数・返金数・振込額。同じ日付の行があれば上書き、無ければ追加し、日付順に並べ直す
「月次」シート：月ごとの売上合計・注文数・売上のあった日数（毎回すべて書き直す）
日付は「2026/10/09」の文字のまま書く（並べ替え・突き合わせを確実にするため）。
書き込み先は初回に自動で作り、ID を amazon_sales_config.json に保存する。
"""

import json
import sys
from datetime import date
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from .aggregate import monthly_summary, to_decimal

BASE_DIR = Path(__file__).resolve().parent.parent
CREDENTIALS_FILE = BASE_DIR / "credentials.json"          # Google Cloud で作った OAuth クライアント（公開しないこと）
TOKEN_FILE = BASE_DIR / "token_sheets.json"               # 課題5-1-1（課題2）と同じログイン情報を使う（公開しないこと）
CONFIG_FILE = BASE_DIR / "amazon_sales_config.json"       # 書き込み先スプレッドシートの ID
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

DAILY_HEADER = ["日付", "曜日", "売上(USD)", "注文数", "返金数", "振込額(USD)"]
MONTHLY_HEADER = ["月", "売上合計(USD)", "注文数", "返金数", "集計日数", "売上のあった日数", "1日平均(USD)"]
WEEKDAYS = "月火水木金土日"
COLUMN_WIDTHS = {"日次": [100, 50, 100, 70, 70, 110], "月次": [90, 120, 70, 70, 80, 130, 110]}   # 各列の幅（ピクセル）


def get_service():
    creds = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CREDENTIALS_FILE.exists():
                sys.exit(f"エラー: {CREDENTIALS_FILE.name} が見つかりません。")
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_FILE), SCOPES)
            creds = flow.run_local_server(port=0)
        TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")
    return build("sheets", "v4", credentials=creds)


def get_spreadsheet_id(service):
    if CONFIG_FILE.exists():
        sid = json.loads(CONFIG_FILE.read_text(encoding="utf-8-sig")).get("spreadsheet_id")
        if sid:
            return sid
    sheet = service.spreadsheets().create(body={
        "properties": {"title": "Amazon日次売上（自動集計）"},
        "sheets": [{"properties": {"title": "日次", "gridProperties": {"frozenRowCount": 1}}},
                   {"properties": {"title": "月次", "gridProperties": {"frozenRowCount": 1}}}],
    }).execute()
    sid = sheet["spreadsheetId"]
    CONFIG_FILE.write_text(json.dumps({"spreadsheet_id": sid}, ensure_ascii=False), encoding="utf-8")
    print(f"✓ スプレッドシートを新しく作成しました（ID を {CONFIG_FILE.name} に保存）")
    return sid


def daily_rows(days):
    return [[d.strftime("%Y/%m/%d"), WEEKDAYS[d.weekday()], float(v["sales"]), v["orders"], v["refunds"], float(v["transfer"])]
            for d, v in sorted(days.items())]


def monthly_rows(months):
    return [[k, float(m["sales"]), m["orders"], m["refunds"], m["days"], m["plus_days"],
             round(float(m["sales"]) / m["days"], 2) if m["days"] else 0] for k, m in months.items()]


def merge_daily(existing, new_rows):
    """シートに既にある行（見出し除く）と新しい行を日付で突き合わせ、新しい方で上書きして日付順に並べる"""
    by_date = {r[0]: r for r in existing if r and r[0]}
    added = sum(1 for r in new_rows if r[0] not in by_date)
    for r in new_rows:
        by_date[r[0]] = r
    return [by_date[k] for k in sorted(by_date)], added


def rows_to_days(rows):
    """「日次」シートの行を {日付: {sales, orders, refunds, transfer}} に戻す（月次の計算用）"""
    days = {}
    for r in rows:
        r = list(r) + [""] * (6 - len(r))
        days[parse_sheet_date(r[0])] = {"sales": to_decimal(str(r[2])), "orders": int(to_decimal(str(r[3]))),
                                        "refunds": int(to_decimal(str(r[4]))), "transfer": to_decimal(str(r[5]))}
    return days


def write(service, sid, days):
    values = service.spreadsheets().values()
    existing = values.get(spreadsheetId=sid, range="日次!A2:F", valueRenderOption="UNFORMATTED_VALUE").execute().get("values", [])
    merged, added = merge_daily(existing, daily_rows(days))
    months = monthly_summary(rows_to_days(merged))   # 前回までの分も含めた「日次」全体から月次を計算し直す
    values.clear(spreadsheetId=sid, range="日次!A:F").execute()
    values.update(spreadsheetId=sid, range="日次!A1", valueInputOption="RAW",
                  body={"values": [DAILY_HEADER] + merged}).execute()
    values.clear(spreadsheetId=sid, range="月次!A:G").execute()
    values.update(spreadsheetId=sid, range="月次!A1", valueInputOption="RAW",
                  body={"values": [MONTHLY_HEADER] + monthly_rows(months)}).execute()
    format_sheets(service, sid)
    return len(merged), added


def format_sheets(service, sid):
    meta = service.spreadsheets().get(spreadsheetId=sid, fields="sheets.properties").execute()
    ids = {s["properties"]["title"]: s["properties"]["sheetId"] for s in meta["sheets"]}
    head = {"backgroundColor": {"red": 0.85, "green": 0.92, "blue": 0.83}, "textFormat": {"bold": True}}
    usd = {"numberFormat": {"type": "NUMBER", "pattern": "#,##0.00;[Red]-#,##0.00"}}
    reqs = []
    for title, money_cols in (("日次", [2, 5]), ("月次", [1, 6])):
        sh = ids[title]
        reqs.append({"repeatCell": {"range": {"sheetId": sh, "startRowIndex": 0, "endRowIndex": 1},
                                    "cell": {"userEnteredFormat": head}, "fields": "userEnteredFormat(backgroundColor,textFormat)"}})
        for c in money_cols:
            reqs.append({"repeatCell": {"range": {"sheetId": sh, "startRowIndex": 1, "startColumnIndex": c, "endColumnIndex": c + 1},
                                        "cell": {"userEnteredFormat": usd}, "fields": "userEnteredFormat.numberFormat"}})
        for i, w in enumerate(COLUMN_WIDTHS[title]):   # 自動調整だと日本語の見出しが切れるので幅は固定
            reqs.append({"updateDimensionProperties": {"range": {"sheetId": sh, "dimension": "COLUMNS", "startIndex": i, "endIndex": i + 1},
                                                       "properties": {"pixelSize": w}, "fields": "pixelSize"}})
    service.spreadsheets().batchUpdate(spreadsheetId=sid, body={"requests": reqs}).execute()


def parse_sheet_date(text):
    y, m, d = (int(x) for x in text.split("/"))
    return date(y, m, d)
