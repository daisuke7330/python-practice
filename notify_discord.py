"""Discord のチャンネルに Webhook で自動通知を送る

使い方:
    python notify_discord.py [--text 本文] [--name 表示名]

引数なしで実行すると、投稿日時入りのテスト通知を送る。
Discord のチャンネル設定 →「連携サービス」→「ウェブフック」で作った URL を discord_config.json に書いておく。
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import requests

BASE_DIR = Path(__file__).resolve().parent
CONFIG_FILE = BASE_DIR / "discord_config.json"  # Webhook URL（知っていれば誰でも投稿できるので公開しないこと）


def load_webhook_url():
    if not CONFIG_FILE.exists():
        sys.exit(
            f"エラー: {CONFIG_FILE.name} が見つかりません。\n"
            "次の形で保存してください。\n"
            '{"webhook_url": "https://discord.com/api/webhooks/..."}'
        )
    url = json.loads(CONFIG_FILE.read_text(encoding="utf-8-sig")).get("webhook_url")  # メモ帳で保存しても読めるように
    if not url:
        sys.exit(f"エラー: {CONFIG_FILE.name} に webhook_url が入っていません。")
    return url


def send_notification(url, text, name):
    # wait=true を付けると、送ったメッセージの情報（ID など）が返ってくる
    res = requests.post(
        url,
        params={"wait": "true"},
        json={"content": text, "username": name},
        timeout=30,
    )
    if res.status_code != 200:
        sys.exit(f"✗ 通知の送信に失敗しました（{res.status_code}: {res.text}）\nWebhook URL が正しいか確認してください。")
    return res.json()


def parse_args():
    parser = argparse.ArgumentParser(description="Discord のチャンネルに Webhook で通知を送ります。")
    parser.add_argument("--text", help="通知する本文（省略時: 送信日時入りのテスト文）")
    parser.add_argument("--name", default="自動通知ボット", help="Discord に表示する送り主の名前（省略時: 自動通知ボット）")
    return parser.parse_args()


def main():
    args = parse_args()
    sent_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    text = args.text or f"Python から Discord に自動通知を送りました。（送信日時: {sent_at}）"
    message = send_notification(load_webhook_url(), text, args.name)

    print("✓ Discord に通知を送りました")
    print(f"    送り主       : {args.name}")
    print(f"    本文         : {text}")
    print(f"    送信日時     : {sent_at}")
    print(f"    メッセージID : {message['id']}")


if __name__ == "__main__":
    main()
