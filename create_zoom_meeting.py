"""Zoom の会議を新しく作り、会議ID・パスワード・会議リンクを表示する

使い方:
    python create_zoom_meeting.py [--topic 会議名] [--start "2026-11-01 10:00"] [--duration 分]

引数なしで実行すると、「テスト会議」という名前で今すぐ始められる会議を作る。
Zoom App Marketplace で作った Server-to-Server OAuth アプリの鍵を zoom_credentials.json に書いておく。
"""

import argparse
import json
import secrets
import string
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

BASE_DIR = Path(__file__).resolve().parent
CREDENTIALS_FILE = BASE_DIR / "zoom_credentials.json"  # Zoom アプリの鍵（公開しないこと）

TOKEN_URL = "https://zoom.us/oauth/token"
API_URL = "https://api.zoom.us/v2"
JST = timezone(timedelta(hours=9))


def load_credentials():
    if not CREDENTIALS_FILE.exists():
        sys.exit(
            f"エラー: {CREDENTIALS_FILE.name} が見つかりません。\n"
            "Zoom App Marketplace で Server-to-Server OAuth アプリを作り、\n"
            "Account ID・Client ID・Client Secret を次の形で保存してください。\n"
            '{"account_id": "...", "client_id": "...", "client_secret": "..."}'
        )
    creds = json.loads(CREDENTIALS_FILE.read_text(encoding="utf-8-sig"))  # メモ帳で保存しても読めるように
    missing = [k for k in ("account_id", "client_id", "client_secret") if not creds.get(k)]
    if missing:
        sys.exit(f"エラー: {CREDENTIALS_FILE.name} に {', '.join(missing)} が入っていません。")
    return creds


def get_access_token(creds):
    # Server-to-Server OAuth は、ブラウザでのログインなしに鍵だけで1時間有効な通行証をもらえる
    res = requests.post(
        TOKEN_URL,
        params={"grant_type": "account_credentials", "account_id": creds["account_id"]},
        auth=(creds["client_id"], creds["client_secret"]),
        timeout=30,
    )
    if res.status_code != 200:
        sys.exit(f"✗ Zoom へのログインに失敗しました（{res.status_code}: {res.text}）\n鍵の値が正しいか確認してください。")
    return res.json()["access_token"]


def make_password(length=8):
    # 会議のパスワード（英数字）。Zoom の上限は10文字
    chars = string.ascii_letters + string.digits
    return "".join(secrets.choice(chars) for _ in range(length))


def create_meeting(token, topic, start=None, duration=30):
    body = {
        "topic": topic,
        "type": 2,  # 2 = 日時を決めた会議
        "duration": duration,
        "timezone": "Asia/Tokyo",
        "password": make_password(),
        "settings": {"join_before_host": True, "waiting_room": False},
    }
    if start:
        body["start_time"] = start.strftime("%Y-%m-%dT%H:%M:%S")

    res = requests.post(
        f"{API_URL}/users/me/meetings",
        headers={"Authorization": f"Bearer {token}"},
        json=body,
        timeout=30,
    )
    if res.status_code != 201:
        sys.exit(f"✗ 会議の作成に失敗しました（{res.status_code}: {res.text}）")
    return res.json()


def to_japan_time(start_time):
    # Zoom は世界標準時（末尾の Z）で返すので、日本時間に直して表示する
    if not start_time:
        return "今すぐ"
    utc = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
    return utc.astimezone(JST).strftime("%Y-%m-%d %H:%M")


def parse_args():
    parser = argparse.ArgumentParser(description="Zoom の会議を作成し、会議ID・パスワード・会議リンクを表示します。")
    parser.add_argument("--topic", default="テスト会議", help="会議名（省略時: テスト会議）")
    parser.add_argument("--start", help='開始日時（例: "2026-11-01 10:00"）。省略すると今すぐ')
    parser.add_argument("--duration", type=int, default=30, help="会議の長さ（分、省略時: 30）")
    return parser.parse_args()


def main():
    args = parse_args()
    start = None
    if args.start:
        try:
            start = datetime.strptime(args.start, "%Y-%m-%d %H:%M")
        except ValueError:
            sys.exit('エラー: --start は "2026-11-01 10:00" の形で入力してください。')

    token = get_access_token(load_credentials())
    meeting = create_meeting(token, args.topic, start, args.duration)

    print("✓ Zoom の会議を作成しました")
    print(f"    会議名     : {meeting['topic']}")
    print(f"    開始日時   : {to_japan_time(meeting.get('start_time'))}")
    print(f"    会議ID     : {meeting['id']}")
    print(f"    パスワード : {meeting['password']}")
    print(f"    会議リンク : {meeting['join_url']}")


if __name__ == "__main__":
    main()
