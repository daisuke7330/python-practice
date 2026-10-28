"""Slack のチャンネルのメッセージを取得し、AI で要約して LINE に送る

使い方:
    python slack_to_line_summary.py [--channel チャンネル] [--hours 時間] [--me 名前] [--dry-run]

引数なしで実行すると、slack_config.json のチャンネルから直近24時間のメッセージを取得し、
Gemini API で要約して、line_config.json の送り先（自分）へ LINE で送る。
--dry-run を付けると、LINE には送らず要約を画面に表示するだけ。

必要な設定ファイル（どれも GitHub には上げない）:
    slack_config.json  : {"bot_token": "xoxb-...", "channel": "#チャンネル名"}
    gemini_config.json : {"api_key": "...", "model": "gemini-3-flash-preview"}
    line_config.json   : {"channel_access_token": "...", "to": "U..."}
Slack アプリには channels:history / channels:read / channels:join / users:read の権限が必要。
"""

import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

import requests

from send_line import push_message

BASE_DIR = Path(__file__).resolve().parent
SLACK_API = "https://slack.com/api/"
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

LINE_MAX_CHARS = 5000  # LINE のテキストメッセージ1通の上限

PROMPT = """あなたは「{me}」さんの秘書です。
次の Slack チャンネルのやり取りを、{me}さんが LINE でさっと読める要約にしてください。

ルール:
- 日本語の自然な文で、全体で400文字以内
- 次の見出しごとに、行頭「・」の箇条書きにする（該当がなければ「なし」）
  【決まったこと】
  【{me}さんのやること・期限】
  【ほかの人の担当】
  【要注意】
- 人の名前・日付・数字は省略しない（例: 12/1（月）17時、20%）
- 雑談やあいさつは入れない
- Markdown の記号（** や #）は使わない（LINE では記号のまま表示されるため）

--- Slack のやり取り（チャンネル: {channel}）---
{messages}
"""


def load_config(name, required_keys):
    path = BASE_DIR / name
    if not path.exists():
        sys.exit(f"エラー: {name} が見つかりません。")
    config = json.loads(path.read_text(encoding="utf-8-sig"))  # メモ帳で保存しても読めるように
    for key in required_keys:
        if not config.get(key):
            sys.exit(f"エラー: {name} に {key} が入っていません。")
    return config


def slack_call(token, method, **params):
    res = requests.get(
        SLACK_API + method,
        headers={"Authorization": f"Bearer {token}"},
        params=params,
        timeout=30,
    )
    data = res.json()
    # Slack はエラーでも HTTP 200 を返すので、ok の値で成否を見る
    if not data.get("ok"):
        hints = {
            "missing_scope": "Slack アプリに権限が足りません。channels:history / channels:read / channels:join / users:read を追加して再インストールしてください。",
            "invalid_auth": "トークンが正しくありません。xoxb- で始まるボットトークンか確認してください。",
            "not_in_channel": "ボットがチャンネルに参加していません。",
        }
        error = data.get("error")
        sys.exit(f"✗ Slack の {method} に失敗しました（{error}）\n{hints.get(error, '')}".rstrip())
    return data


def find_channel_id(token, channel):
    if not channel.startswith("#"):
        return channel  # ID（C で始まる）を直接指定した場合
    name = channel.lstrip("#")
    data = slack_call(token, "conversations.list", types="public_channel", limit=1000)
    for ch in data["channels"]:
        if ch["name"] == name:
            if not ch.get("is_member"):
                # 公開チャンネルの履歴を読むにはボットが参加している必要がある
                requests.post(
                    SLACK_API + "conversations.join",
                    headers={"Authorization": f"Bearer {token}"},
                    data={"channel": ch["id"]},
                    timeout=30,
                )
            return ch["id"]
    sys.exit(f"エラー: チャンネル {channel} が見つかりません。")


def fetch_messages(token, channel_id, hours):
    oldest = (datetime.now() - timedelta(hours=hours)).timestamp()
    data = slack_call(token, "conversations.history", channel=channel_id, oldest=oldest, limit=200)
    names = {}  # ユーザーIDごとの表示名（同じ人を何度も問い合わせない）
    lines = []
    for msg in reversed(data["messages"]):  # 新しい順で届くので、古い順に並べ替える
        if msg.get("subtype") in ("channel_join", "channel_leave"):
            continue
        if msg.get("user"):
            if msg["user"] not in names:
                info = slack_call(token, "users.info", user=msg["user"])["user"]
                names[msg["user"]] = info.get("real_name") or info.get("name")
            who = names[msg["user"]]
        else:
            who = msg.get("username") or msg.get("bot_profile", {}).get("name", "bot")
        time = datetime.fromtimestamp(float(msg["ts"])).strftime("%m/%d %H:%M")
        lines.append(f"[{time}] {who}: {msg.get('text', '')}")
    return lines


def summarize(api_key, model, channel, lines, me):
    res = requests.post(
        GEMINI_URL.format(model=model),
        headers={"x-goog-api-key": api_key},
        json={"contents": [{"parts": [{"text": PROMPT.format(me=me, channel=channel, messages="\n".join(lines))}]}]},
        timeout=120,
    )
    if res.status_code != 200:
        hints = {
            400: "API キーか送った内容に問題があります。gemini_config.json の api_key を確認してください。",
            403: "API キーが使えません。Google AI Studio でキーを発行し直してください。",
            404: "モデル名が見つかりません。gemini_config.json の model を確認してください。",
            429: "無料枠の回数制限に達しました。少し待ってから実行してください。",
        }
        sys.exit(f"✗ 要約に失敗しました（{res.status_code}: {res.text[:200]}）\n{hints.get(res.status_code, '')}".rstrip())
    return res.json()["candidates"][0]["content"]["parts"][0]["text"].strip()


def parse_args():
    parser = argparse.ArgumentParser(description="Slack のメッセージを要約して LINE に送ります。")
    parser.add_argument("--channel", help="取得するチャンネル（省略時: slack_config.json の channel）")
    parser.add_argument("--hours", type=float, default=24, help="何時間前までのメッセージを取るか（既定: 24）")
    parser.add_argument("--me", default="黒田", help="要約を読む人の名前（その人のやることを分けて書く。既定: 黒田）")
    parser.add_argument("--dry-run", action="store_true", help="LINE には送らず、要約を表示するだけ")
    return parser.parse_args()


def main():
    args = parse_args()
    slack = load_config("slack_config.json", ["bot_token"])
    gemini = load_config("gemini_config.json", ["api_key"])
    channel = args.channel or slack.get("channel")
    if not channel:
        sys.exit("エラー: チャンネルを --channel か slack_config.json の channel で指定してください。")

    channel_id = find_channel_id(slack["bot_token"], channel)
    lines = fetch_messages(slack["bot_token"], channel_id, args.hours)
    print(f"✓ Slack {channel} から {len(lines)} 件のメッセージを取得しました（直近 {args.hours:g} 時間）")
    if not lines:
        sys.exit("要約するメッセージがありません。--hours を長くしてみてください。")

    model = gemini.get("model", "gemini-3-flash-preview")
    summary = summarize(gemini["api_key"], model, channel, lines, args.me)
    print(f"✓ {model} で要約しました（{len(summary)} 文字）\n")

    now = datetime.now().strftime("%m/%d %H:%M")
    text = f"📋 Slack {channel} の要約（{now}・{len(lines)}件）\n\n{summary}"[:LINE_MAX_CHARS]
    print(text)

    if args.dry_run:
        print("\n（--dry-run のため LINE には送っていません）")
        return
    line = load_config("line_config.json", ["channel_access_token", "to"])
    request_id = push_message(line["channel_access_token"], line["to"], text)
    print(f"\n✓ LINE に要約を送りました（リクエストID: {request_id}）")


if __name__ == "__main__":
    main()
