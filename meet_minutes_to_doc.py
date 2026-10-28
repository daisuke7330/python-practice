"""会議の録音から議事録を作り、Google ドキュメントに保存する

使い方:
    python meet_minutes_to_doc.py [--audio 音声ファイル] [--title 会議名] [--members 参加者]

Google Meet の録音（または手元の会議音声）を Gemini API で文字起こしし、
その文字起こしから議事録（決定事項・ToDo・次回予定など）を作って、
Google ドキュメントに「議事録＋文字起こし全文」を書き込む。
文字起こしと議事録はテキストファイル（minutes_日時.txt）にも残す。

使う設定ファイル:
    gemini_config.json : {"api_key": "...", "model": "gemini-3-flash-preview"}
    credentials.json / token.json : create_google_doc.py と同じ Google のログイン情報
"""

import argparse
import base64
import json
import mimetypes
import sys
from datetime import datetime
from pathlib import Path

import requests
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from create_google_doc import create_document, get_credentials

BASE_DIR = Path(__file__).resolve().parent
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
INLINE_LIMIT = 18 * 1024 * 1024  # これより大きい音声は1回の送信に入らない

TRANSCRIBE_PROMPT = """この会議の音声を、日本語で文字起こししてください。
ルール:
- 話す人が変わるごとに改行し、行頭に「名前: 」を付ける
- 名前は会話の中で呼ばれている名前を使う。分からなければ「話者A」「話者B」とする
{members}- 「えー」「あの」などの言いよどみは省く。それ以外は言い換えず、話したとおりに書く
- 文字起こし以外の前置きや説明は書かない"""

MINUTES_PROMPT = """次の会議の文字起こしから、社内共有用の議事録を作ってください。
ルール:
- 次の見出しを使い、見出しの行頭には「■」を付ける。中身は行頭「・」の箇条書き
  ■会議の概要（会議名・日付・参加者）
  ■議題
  ■決定事項
  ■ToDo（担当者・期限）
  ■懸念点・注意点
  ■次回予定
- 日付・時刻・数字・担当者は省略しない
- 文字起こしに無いことは書かない（分からない項目は「なし」）
- Markdown の記号（** や #）は使わない
会議名: {title}
日付: {date}

--- 文字起こし ---
{transcript}
"""


def load_gemini():
    path = BASE_DIR / "gemini_config.json"
    if not path.exists():
        sys.exit("エラー: gemini_config.json が見つかりません。")
    config = json.loads(path.read_text(encoding="utf-8-sig"))
    if not config.get("api_key"):
        sys.exit("エラー: gemini_config.json に api_key が入っていません。")
    return config["api_key"], config.get("model", "gemini-3-flash-preview")


def ask_gemini(api_key, model, parts):
    res = requests.post(
        GEMINI_URL.format(model=model),
        headers={"x-goog-api-key": api_key},
        json={"contents": [{"parts": parts}]},
        timeout=300,
    )
    if res.status_code != 200:
        hints = {
            400: "送った音声の形式か API キーを確認してください。",
            429: "無料枠の回数制限に達しました。少し待ってから実行してください。",
        }
        sys.exit(f"✗ Gemini API でエラーになりました（{res.status_code}: {res.text[:200]}）\n{hints.get(res.status_code, '')}".rstrip())
    return res.json()["candidates"][0]["content"]["parts"][0]["text"].strip()


def transcribe(api_key, model, audio_path, members):
    data = audio_path.read_bytes()
    if len(data) > INLINE_LIMIT:
        sys.exit("エラー: 音声ファイルが大きすぎます（18MB まで）。短く分けてから実行してください。")
    mime = mimetypes.guess_type(audio_path.name)[0] or "audio/wav"
    audio = {"inlineData": {"mimeType": mime, "data": base64.b64encode(data).decode()}}
    # 参加者が分かっていれば伝えて、「話者B」ではなく名前で書いてもらう
    hint = f"- 参加者は {members} です。呼ばれていない人も、話の内容から当てはめる\n" if members else ""
    return ask_gemini(api_key, model, [{"text": TRANSCRIBE_PROMPT.format(members=hint)}, audio])


def write_document(service, title, minutes, transcript):
    doc_id = create_document(service, title)
    body = f"{title}\n\n{minutes}\n\n■文字起こし（全文）\n{transcript}\n"
    requests_ = [{"insertText": {"location": {"index": 1}, "text": body}}]

    # 1行目をタイトル、「■」で始まる行を見出しの書式にする
    index = 1
    for i, line in enumerate(body.split("\n")):
        end = index + len(line) + 1
        style = "TITLE" if i == 0 else "HEADING_2" if line.startswith("■") else None
        if style:
            requests_.append({"updateParagraphStyle": {
                "range": {"startIndex": index, "endIndex": end},
                "paragraphStyle": {"namedStyleType": style}, "fields": "namedStyleType"}})
        index = end
    service.documents().batchUpdate(documentId=doc_id, body={"requests": requests_}).execute()
    return doc_id


def parse_args():
    parser = argparse.ArgumentParser(description="会議の録音から議事録を作り、Google ドキュメントに保存します。")
    parser.add_argument("--audio", type=Path, default=BASE_DIR / "sample_meeting.wav", help="会議の音声ファイル（既定: sample_meeting.wav）")
    parser.add_argument("--title", default="定例会議", help="会議名（既定: 定例会議）")
    parser.add_argument("--members", help="参加者の名前（例: 山本,黒田）。話者の名前を当てはめるのに使う")
    return parser.parse_args()


def main():
    args = parse_args()
    if not args.audio.is_file():
        sys.exit(f"エラー: {args.audio} が見つかりません。")
    api_key, model = load_gemini()
    now = datetime.now()

    print(f"… {args.audio.name} を文字起こししています（{model}）")
    transcript = transcribe(api_key, model, args.audio, args.members)
    print(f"✓ 文字起こしができました（{len(transcript.splitlines())} 行・{len(transcript)} 文字）")

    minutes = ask_gemini(api_key, model, [{"text": MINUTES_PROMPT.format(
        title=args.title, date=now.strftime("%Y-%m-%d"), transcript=transcript)}])
    print(f"✓ 議事録ができました（{len(minutes)} 文字）\n")
    print(minutes)

    local = BASE_DIR / f"minutes_{now:%Y%m%d_%H%M}.txt"
    local.write_text(f"{minutes}\n\n■文字起こし（全文）\n{transcript}\n", encoding="utf-8")

    title = f"議事録_{now:%Y-%m-%d}_{args.title}"
    service = build("docs", "v1", credentials=get_credentials())
    try:
        doc_id = write_document(service, title, minutes, transcript)
    except HttpError as e:
        sys.exit(f"✗ ドキュメントの作成に失敗しました（{e.status_code}: {e.reason}）")

    print(f"\n✓ Google ドキュメント「{title}」に保存しました（手元にも {local.name} を保存）")
    print(f"    URL : https://docs.google.com/document/d/{doc_id}/edit")


if __name__ == "__main__":
    main()
