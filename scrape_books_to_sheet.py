"""EC サイトの商品データを取得・加工して Google スプレッドシートに保存する

使い方:
    python scrape_books_to_sheet.py [--category カテゴリ] [--rate 為替レート] [--low 在庫の下限]

スクレイピング練習用に公開されている書店サイト books.toscrape.com から、
指定カテゴリの商品（タイトル・価格・在庫数・評価）を取得し、
円換算・在庫判定などを加えて Google スプレッドシートに書き込む。
実行するたびに「取得日時のシート」を追加し、「履歴」シートに1行ずつ集計を残すので、
定期的に実行すると価格や在庫の推移を追える。

初回はブラウザで Google にログインして許可する（token_sheets.json が作られる）。
書き込み先のスプレッドシートは初回に自動で作成し、ID を sheets_config.json に保存する。
"""

import argparse
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

BASE_DIR = Path(__file__).resolve().parent
CREDENTIALS_FILE = BASE_DIR / "credentials.json"   # Google Cloud で作った OAuth クライアント（公開しないこと）
TOKEN_FILE = BASE_DIR / "token_sheets.json"        # ログイン後に保存されるトークン（公開しないこと）
CONFIG_FILE = BASE_DIR / "sheets_config.json"      # 書き込み先スプレッドシートの ID
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

SITE = "https://books.toscrape.com/"
RATINGS = {"One": 1, "Two": 2, "Three": 3, "Four": 4, "Five": 5}
HEADER = ["No", "タイトル", "価格(£)", "価格(円)", "価格帯", "在庫数", "在庫判定", "評価(★)", "UPC", "商品URL"]
COLUMN_WIDTHS = [40, 360, 70, 80, 60, 60, 80, 80, 140, 300]  # HEADER の各列の幅（ピクセル）
HISTORY_HEADER = ["取得日時", "カテゴリ", "商品数", "平均価格(円)", "最安(円)", "最高(円)", "在庫合計", "要発注の商品数"]


# ---------- 1. 取得（スクレイピング） ----------

def get_soup(url):
    res = requests.get(url, timeout=30)
    res.raise_for_status()
    res.encoding = "utf-8"
    return BeautifulSoup(res.text, "html.parser")


def find_category_url(category):
    soup = get_soup(SITE)
    for a in soup.select("div.side_categories ul li ul li a"):
        if a.get_text(strip=True).lower() == category.lower():
            return urljoin(SITE, a["href"])
    names = [a.get_text(strip=True) for a in soup.select("div.side_categories ul li ul li a")]
    sys.exit(f"エラー: カテゴリ「{category}」が見つかりません。\n使えるカテゴリ: {', '.join(names)}")


def fetch_products(category_url, limit):
    products = []
    url = category_url
    while url and len(products) < limit:
        soup = get_soup(url)
        for item in soup.select("article.product_pod"):
            link = urljoin(url, item.h3.a["href"])
            products.append({
                "title": item.h3.a["title"],
                "price": float(item.select_one("p.price_color").get_text().replace("£", "").replace("Â", "")),
                "rating": RATINGS.get(item.select_one("p.star-rating")["class"][1], 0),
                "url": link,
            })
        next_link = soup.select_one("li.next a")
        url = urljoin(url, next_link["href"]) if next_link else None
    products = products[:limit]

    # 一覧ページには在庫「数」が無いので、商品ページを1件ずつ開いて取る
    for p in products:
        detail = get_soup(p["url"])
        table = {th.get_text(): td.get_text() for th, td in zip(detail.select("table th"), detail.select("table td"))}
        m = re.search(r"\((\d+) available\)", table.get("Availability", ""))
        p["stock"] = int(m.group(1)) if m else 0
        p["upc"] = table.get("UPC", "")
        time.sleep(0.3)  # サイトに負荷をかけないよう間をあける
    return products


# ---------- 2. 加工 ----------

def price_band(yen):
    if yen < 5000:
        return "低"
    if yen < 9000:
        return "中"
    return "高"


def to_rows(products, rate, low):
    rows = []
    for i, p in enumerate(sorted(products, key=lambda x: x["stock"]), start=1):  # 在庫が少ない順
        yen = round(p["price"] * rate)
        rows.append([
            i, p["title"], p["price"], yen, price_band(yen), p["stock"],
            "要発注" if p["stock"] <= low else "OK",
            "★" * p["rating"], p["upc"], p["url"],
        ])
    return rows


# ---------- 3. 保存（Google スプレッドシート） ----------

def get_credentials():
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
    return creds


def get_spreadsheet_id(service):
    if CONFIG_FILE.exists():
        config = json.loads(CONFIG_FILE.read_text(encoding="utf-8-sig"))
        if config.get("spreadsheet_id"):
            return config["spreadsheet_id"]
    sheet = service.spreadsheets().create(body={
        "properties": {"title": "EC商品データ（books.toscrape.com）"},
        "sheets": [{"properties": {"title": "履歴"}}],
    }).execute()
    sid = sheet["spreadsheetId"]
    service.spreadsheets().values().update(
        spreadsheetId=sid, range="履歴!A1", valueInputOption="RAW", body={"values": [HISTORY_HEADER]},
    ).execute()
    CONFIG_FILE.write_text(json.dumps({"spreadsheet_id": sid}, ensure_ascii=False), encoding="utf-8")
    print(f"✓ スプレッドシートを新しく作成しました（ID を {CONFIG_FILE.name} に保存）")
    return sid


def write_sheet(service, sid, sheet_name, rows, low_col_count):
    # 取得日時の名前でシートを追加し、表を書き込む
    added = service.spreadsheets().batchUpdate(spreadsheetId=sid, body={
        "requests": [{"addSheet": {"properties": {"title": sheet_name, "index": 0}}}],
    }).execute()
    sheet_id = added["replies"][0]["addSheet"]["properties"]["sheetId"]
    service.spreadsheets().values().update(
        spreadsheetId=sid, range=f"'{sheet_name}'!A1", valueInputOption="USER_ENTERED",
        body={"values": [HEADER] + rows},
    ).execute()

    red = {"red": 0.96, "green": 0.8, "blue": 0.8}
    service.spreadsheets().batchUpdate(spreadsheetId=sid, body={"requests": [
        # 見出しを太字・色付きにして固定
        {"repeatCell": {
            "range": {"sheetId": sheet_id, "startRowIndex": 0, "endRowIndex": 1},
            "cell": {"userEnteredFormat": {"textFormat": {"bold": True, "foregroundColor": {"red": 1, "green": 1, "blue": 1}},
                                           "backgroundColor": {"red": 0.2, "green": 0.4, "blue": 0.7}}},
            "fields": "userEnteredFormat(textFormat,backgroundColor)"}},
        {"updateSheetProperties": {"properties": {"sheetId": sheet_id, "gridProperties": {"frozenRowCount": 1}},
                                   "fields": "gridProperties.frozenRowCount"}},
        # 円の列を3桁区切りに
        {"repeatCell": {
            "range": {"sheetId": sheet_id, "startRowIndex": 1, "startColumnIndex": 3, "endColumnIndex": 4},
            "cell": {"userEnteredFormat": {"numberFormat": {"type": "NUMBER", "pattern": "#,##0"}}},
            "fields": "userEnteredFormat.numberFormat"}},
        # 要発注の行を赤くする
        {"addConditionalFormatRule": {"index": 0, "rule": {
            "ranges": [{"sheetId": sheet_id, "startRowIndex": 1, "startColumnIndex": 0, "endColumnIndex": len(HEADER)}],
            "booleanRule": {"condition": {"type": "CUSTOM_FORMULA", "values": [{"userEnteredValue": '=$G2="要発注"'}]},
                            "format": {"backgroundColor": red}}}}},
    ] + [
        # 列幅をそろえる（自動調整だと長いタイトルに引っ張られて数字の列がつぶれるため）
        {"updateDimensionProperties": {
            "range": {"sheetId": sheet_id, "dimension": "COLUMNS", "startIndex": i, "endIndex": i + 1},
            "properties": {"pixelSize": width}, "fields": "pixelSize"}}
        for i, width in enumerate(COLUMN_WIDTHS)
    ]}).execute()


def append_history(service, sid, when, category, rows):
    yens = [r[3] for r in rows]
    summary = [when, category, len(rows), round(sum(yens) / len(yens)), min(yens), max(yens),
               sum(r[5] for r in rows), sum(1 for r in rows if r[6] == "要発注")]
    service.spreadsheets().values().append(
        spreadsheetId=sid, range="履歴!A1", valueInputOption="USER_ENTERED", body={"values": [summary]},
    ).execute()
    format_history(service, sid)
    return summary


def format_history(service, sid):
    # 「履歴」シートの見出し・列幅・3桁区切りを整える（何度実行しても同じ見た目になる）
    meta = service.spreadsheets().get(spreadsheetId=sid).execute()
    sheet_id = next(s["properties"]["sheetId"] for s in meta["sheets"] if s["properties"]["title"] == "履歴")
    widths = [130, 90, 70, 100, 80, 80, 80, 110]
    service.spreadsheets().batchUpdate(spreadsheetId=sid, body={"requests": [
        {"repeatCell": {
            "range": {"sheetId": sheet_id, "startRowIndex": 0, "endRowIndex": 1},
            "cell": {"userEnteredFormat": {"textFormat": {"bold": True, "foregroundColor": {"red": 1, "green": 1, "blue": 1}},
                                           "backgroundColor": {"red": 0.2, "green": 0.4, "blue": 0.7}}},
            "fields": "userEnteredFormat(textFormat,backgroundColor)"}},
        {"updateSheetProperties": {"properties": {"sheetId": sheet_id, "gridProperties": {"frozenRowCount": 1}},
                                   "fields": "gridProperties.frozenRowCount"}},
        {"repeatCell": {
            "range": {"sheetId": sheet_id, "startRowIndex": 1, "startColumnIndex": 2, "endColumnIndex": 8},
            "cell": {"userEnteredFormat": {"numberFormat": {"type": "NUMBER", "pattern": "#,##0"}}},
            "fields": "userEnteredFormat.numberFormat"}},
    ] + [
        {"updateDimensionProperties": {
            "range": {"sheetId": sheet_id, "dimension": "COLUMNS", "startIndex": i, "endIndex": i + 1},
            "properties": {"pixelSize": width}, "fields": "pixelSize"}}
        for i, width in enumerate(widths)
    ]}).execute()


def parse_args():
    parser = argparse.ArgumentParser(description="EC サイトの商品データを取得・加工してスプレッドシートに保存します。")
    parser.add_argument("--category", default="Business", help="カテゴリ名（既定: Business）")
    parser.add_argument("--limit", type=int, default=20, help="取得する商品数の上限（既定: 20）")
    parser.add_argument("--rate", type=float, default=200, help="1ポンドあたりの円（既定: 200）")
    parser.add_argument("--low", type=int, default=5, help="この数以下なら「要発注」（既定: 5）")
    return parser.parse_args()


def main():
    args = parse_args()
    now = datetime.now()

    category_url = find_category_url(args.category)
    products = fetch_products(category_url, args.limit)
    print(f"✓ {args.category} の商品を {len(products)} 件取得しました")
    if not products:
        sys.exit("商品がありませんでした。")

    rows = to_rows(products, args.rate, args.low)

    service = build("sheets", "v4", credentials=get_credentials())
    sid = get_spreadsheet_id(service)
    sheet_name = now.strftime("%m%d_%H%M") + "_" + args.category
    write_sheet(service, sid, sheet_name, rows, args.low)
    summary = append_history(service, sid, now.strftime("%Y-%m-%d %H:%M"), args.category, rows)

    print(f"✓ シート「{sheet_name}」に書き込みました（在庫が少ない順）")
    for r in rows[:5]:
        print(f"    {r[0]:>2}. {r[1][:40]:<40} {r[3]:>6,}円  在庫 {r[5]:>2}  {r[6]}")
    if len(rows) > 5:
        print(f"    …ほか {len(rows) - 5} 件")
    print(f"✓ 履歴に追加: 平均 {summary[3]:,}円 / 在庫合計 {summary[6]} / 要発注 {summary[7]} 件")
    print(f"    URL: https://docs.google.com/spreadsheets/d/{sid}/edit")


if __name__ == "__main__":
    main()
