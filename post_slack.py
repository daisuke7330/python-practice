"""Slack の指定チャンネルにメッセージを投稿する

使い方:
    python post_slack.py [--channel チャンネル] [--text 本文]

引数なしで実行すると、slack_config.json に書いたチャンネルへテスト文を投稿する。
Slack API で作ったアプリのボットトークン（xoxb- で始まる）を slack_config.json に書いておく。
ボットは投稿先のチャンネルに招待しておく（/invite @アプリ名）。
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import requests

BASE_DIR = Path(__file__).resolve().parent
CONFIG_FILE = BASE_DIR / "slack_config.json"  # ボットトークン（公開しないこと）と投稿先チャンネル

POST_URL = "https://slack.com/api/chat.postMessage"


def load_config():
    if not CONFIG_FILE.exists():
        sys.exit(
            f"エラー: {CONFIG_FILE.name} が見つかりません。\n"
            "次の形で保存してください。\n"
            '{"bot_token": "xoxb-...", "channel": "#チャンネル名"}'
        )
    config = json.loads(CONFIG_FILE.read_text(encoding="utf-8-sig"))  # メモ帳で保存しても読めるように
    if not config.get("bot_token"):
        sys.exit(f"エラー: {CONFIG_FILE.name} に bot_token が入っていません。")
    return config


def post_message(token, channel, text, username=None, icon_emoji=None):
    payload = {"channel": channel, "text": text}
    if username:
        # 投稿者名とアイコンを変える（chat:write.customize の権限が必要）
        payload.update({"username": username, "icon_emoji": icon_emoji})
    res = requests.post(
        POST_URL,
        headers={"Authorization": f"Bearer {token}"},
        json=payload,
        timeout=30,
    )
    data = res.json()
    # Slack はエラーでも HTTP 200 を返すので、ok の値で成否を見る
    if not data.get("ok"):
        hints = {
            "not_in_channel": "ボットがチャンネルに参加していません。チャンネルで /invite @アプリ名 を実行してください。",
            "channel_not_found": "チャンネルが見つかりません。チャンネル名か ID を確認してください。",
            "invalid_auth": "トークンが正しくありません。xoxb- で始まるボットトークンか確認してください。",
            "missing_scope": "アプリに chat:write の権限がありません。権限を追加してアプリを再インストールしてください。",
        }
        error = data.get("error")
        sys.exit(f"✗ 投稿に失敗しました（{error}）\n{hints.get(error, '')}".rstrip())
    return data


def parse_args():
    parser = argparse.ArgumentParser(description="Slack の指定チャンネルにメッセージを投稿します。")
    parser.add_argument("--channel", help="投稿先チャンネル（例: #general。省略時: slack_config.json の channel）")
    parser.add_argument("--text", help="投稿する本文（省略時: 投稿日時入りのテスト文）")
    return parser.parse_args()


def main():
    args = parse_args()
    config = load_config()
    channel = args.channel or config.get("channel")
    if not channel:
        sys.exit("エラー: 投稿先チャンネルを --channel か slack_config.json の channel で指定してください。")

    posted_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    text = args.text or f"Python から Slack API を使って投稿しました。（投稿日時: {posted_at}）"
    data = post_message(config["bot_token"], channel, text)

    print("✓ Slack に投稿しました")
    print(f"    チャンネル : {channel}")
    print(f"    本文       : {text}")
    print(f"    投稿日時   : {posted_at}")
    print(f"    メッセージ : ts={data['ts']}")


if __name__ == "__main__":
    main()
