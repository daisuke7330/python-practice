"""Discord のチャンネルに Webhook で自動通知を送る

使い方:
    python notify_discord.py [--text 本文] [--name 表示名]
    python notify_discord.py --title 見出し [--field 項目=値 ...] [--color 色] [--image 画像ファイル]

引数なしで実行すると、投稿日時入りのテスト通知を送る。
--title を付けると、色付きのカード（埋め込み）で見出し・項目・画像をまとめて通知する。
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


COLORS = {"blue": 0x3498DB, "green": 0x2ECC71, "orange": 0xE67E22, "red": 0xE74C3C}  # カード左端の線の色


def build_embed(title, text, fields, color, image, sent_at):
    # 埋め込み（embed）にすると、見出し・項目・画像を1枚のカードにまとめて表示できる
    embed = {
        "title": title,
        "description": text,
        "color": COLORS[color],
        "fields": [{"name": k, "value": v, "inline": True} for k, v in fields],
        "footer": {"text": f"送信日時: {sent_at}"},
    }
    if image:
        embed["image"] = {"url": f"attachment://{image.name}"}  # 添付した画像をカードの中に表示する
    return embed


def send_notification(url, payload, image=None):
    # wait=true を付けると、送ったメッセージの情報（ID など）が返ってくる
    if image:
        # 画像を付けるときは、本文（payload_json）とファイルを multipart でまとめて送る
        with image.open("rb") as f:
            res = requests.post(
                url,
                params={"wait": "true"},
                data={"payload_json": json.dumps(payload, ensure_ascii=False)},
                files={"files[0]": (image.name, f)},
                timeout=60,
            )
    else:
        res = requests.post(url, params={"wait": "true"}, json=payload, timeout=30)
    if res.status_code != 200:
        sys.exit(f"✗ 通知の送信に失敗しました（{res.status_code}: {res.text}）\nWebhook URL が正しいか確認してください。")
    return res.json()


def parse_field(value):
    if "=" not in value:
        raise argparse.ArgumentTypeError("--field は「項目=値」の形で指定してください（例: 売上=120万円）")
    key, val = value.split("=", 1)
    return key.strip(), val.strip()


def parse_args():
    parser = argparse.ArgumentParser(description="Discord のチャンネルに Webhook で通知を送ります。")
    parser.add_argument("--text", help="通知する本文（省略時: 送信日時入りのテスト文）")
    parser.add_argument("--name", default="自動通知ボット", help="Discord に表示する送り主の名前（省略時: 自動通知ボット）")
    parser.add_argument("--title", help="カードの見出し（付けるとカード形式で送る）")
    parser.add_argument("--field", type=parse_field, action="append", default=[], help="カードに並べる項目（「項目=値」、何個でも可）")
    parser.add_argument("--color", default="blue", choices=COLORS, help="カードの色（省略時: blue）")
    parser.add_argument("--image", type=Path, help="添付する画像ファイル（カード形式のときはカードの中に表示）")
    return parser.parse_args()


def main():
    args = parse_args()
    if args.image and not args.image.exists():
        sys.exit(f"エラー: 画像ファイルが見つかりません: {args.image}")

    sent_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    payload = {"username": args.name}
    if args.title:
        payload["embeds"] = [build_embed(args.title, args.text or "", args.field, args.color, args.image, sent_at)]
        text = args.text or ""
    else:
        text = args.text or f"Python から Discord に自動通知を送りました。（送信日時: {sent_at}）"
        payload["content"] = text
    message = send_notification(load_webhook_url(), payload, args.image)

    print("✓ Discord に通知を送りました")
    print(f"    送り主       : {args.name}")
    if args.title:
        print(f"    見出し       : {args.title}（カード形式・{args.color}）")
        for k, v in args.field:
            print(f"    項目         : {k} = {v}")
    if text:
        print(f"    本文         : {text}")
    if args.image:
        print(f"    添付画像     : {args.image.name}")
    print(f"    送信日時     : {sent_at}")
    print(f"    メッセージID : {message['id']}")


if __name__ == "__main__":
    main()
