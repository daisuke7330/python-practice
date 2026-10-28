"""LINE 公式アカウントからメッセージを送る（LINE Messaging API）

使い方:
    python send_line.py [--text 本文] [--to ユーザーID]

引数なしで実行すると、line_config.json に書いた送り先（自分のユーザーID）へテスト文を送る。
LINE Developers のチャネルで発行した「チャネルアクセストークン（長期）」と、
「あなたのユーザーID」（U で始まる）を line_config.json に書いておく。
送り先の人は、公式アカウントを友だち追加しておく必要がある。
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import requests

BASE_DIR = Path(__file__).resolve().parent
CONFIG_FILE = BASE_DIR / "line_config.json"  # チャネルアクセストークン（公開しないこと）と送り先

PUSH_URL = "https://api.line.me/v2/bot/message/push"


def load_config():
    if not CONFIG_FILE.exists():
        sys.exit(
            f"エラー: {CONFIG_FILE.name} が見つかりません。\n"
            "次の形で保存してください。\n"
            '{"channel_access_token": "...", "to": "U..."}'
        )
    config = json.loads(CONFIG_FILE.read_text(encoding="utf-8-sig"))  # メモ帳で保存しても読めるように
    if not config.get("channel_access_token"):
        sys.exit(f"エラー: {CONFIG_FILE.name} に channel_access_token が入っていません。")
    return config


def push_message(token, to, text):
    # プッシュメッセージ：相手からの話しかけを待たずに、こちらから送る
    res = requests.post(
        PUSH_URL,
        headers={"Authorization": f"Bearer {token}"},
        json={"to": to, "messages": [{"type": "text", "text": text}]},
        timeout=30,
    )
    if res.status_code != 200:
        hints = {
            400: "送り先のユーザーIDが正しいか、公式アカウントを友だち追加しているか確認してください。",
            401: "チャネルアクセストークンが正しくありません。発行し直して貼り直してください。",
            429: "送信できる上限に達しました。無料プランは月の送信数に上限があります。",
        }
        sys.exit(f"✗ 送信に失敗しました（{res.status_code}: {res.text}）\n{hints.get(res.status_code, '')}".rstrip())
    return res.headers.get("x-line-request-id", "")


def parse_args():
    parser = argparse.ArgumentParser(description="LINE 公式アカウントからメッセージを送ります。")
    parser.add_argument("--text", help="送る本文（省略時: 送信日時入りのテスト文）")
    parser.add_argument("--to", help="送り先のユーザーID（省略時: line_config.json の to）")
    return parser.parse_args()


def main():
    args = parse_args()
    config = load_config()
    to = args.to or config.get("to")
    if not to:
        sys.exit("エラー: 送り先を --to か line_config.json の to で指定してください。")

    sent_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    text = args.text or f"Python から LINE Messaging API を使って送りました。（送信日時: {sent_at}）"
    request_id = push_message(config["channel_access_token"], to, text)

    print("✓ LINE にメッセージを送りました")
    print(f"    送り先       : {to[:6]}…（ユーザーID）")
    print(f"    本文         : {text}")
    print(f"    送信日時     : {sent_at}")
    print(f"    リクエストID : {request_id}")


if __name__ == "__main__":
    main()
