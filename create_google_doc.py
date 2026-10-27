"""Google ドキュメントを新しく作り、指定したテキストを書き込む

使い方:
    python create_google_doc.py [--title タイトル] [--text 本文 | --file テキストファイル]

本文を指定せずに実行すると、タイトルと本文を聞かれる。
upload_to_drive.py と同じ credentials.json / token.json を使う。
初回はブラウザが開くので、Google アカウントでログインして許可する。
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

BASE_DIR = Path(__file__).resolve().parent
CREDENTIALS_FILE = BASE_DIR / "credentials.json"  # Google Cloud で作った OAuth クライアントの鍵
TOKEN_FILE = BASE_DIR / "token.json"  # 2回目以降ログインを省略するための保存ファイル

# このアプリが作ったファイルだけを扱える権限。Docs API の作成・書き込みもこれで足りる
SCOPES = ["https://www.googleapis.com/auth/drive.file"]


def get_credentials():
    creds = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
        except RefreshError:
            creds = None  # 保存したログインが失効していたら、ログインし直す

    if not (creds and creds.valid):
        if not CREDENTIALS_FILE.exists():
            sys.exit(
                f"エラー: {CREDENTIALS_FILE.name} が見つかりません。\n"
                "Google Cloud Console で OAuth クライアント（デスクトップ アプリ）を作成し、\n"
                f"ダウンロードした JSON を {CREDENTIALS_FILE} に置いてください。"
            )
        flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_FILE), SCOPES)
        creds = flow.run_local_server(port=0)  # ブラウザが開いてログイン・許可を求める

    TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")
    return creds


def create_document(service, title):
    # 新しい空のドキュメントを作り、その ID を受け取る
    doc = service.documents().create(body={"title": title}).execute()
    return doc["documentId"]


def insert_text(service, document_id, text):
    # 本文の先頭は index 1（0 はドキュメント自体の開始位置）
    requests = [{"insertText": {"location": {"index": 1}, "text": text}}]
    service.documents().batchUpdate(
        documentId=document_id, body={"requests": requests}
    ).execute()


def parse_args():
    parser = argparse.ArgumentParser(description="Google ドキュメントを作成してテキストを挿入します。")
    parser.add_argument("--title", help="ドキュメントのタイトル（省略すると日時入りの名前）")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--text", help="挿入するテキスト")
    group.add_argument("--file", type=Path, help="挿入するテキストが入ったファイル（UTF-8）")
    args = parser.parse_args()

    if args.file:
        if not args.file.is_file():
            sys.exit(f"エラー: {args.file} が見つかりません。")
        args.text = args.file.read_text(encoding="utf-8")

    if args.text is None:
        # 実行ボタンから起動したときは引数がないので、ここで聞く
        if args.title is None:
            args.title = input("タイトルを入力してください（空なら自動）: ").strip()
        print("挿入するテキストを入力してください（空行で終了）:")
        lines = []
        while (line := input()) != "":
            lines.append(line)
        args.text = "\n".join(lines)

    if not args.title:
        args.title = f"新しいドキュメント {datetime.now():%Y-%m-%d %H:%M}"
    return args


def main():
    args = parse_args()
    if not args.text:
        sys.exit("テキストが指定されていません。")

    service = build("docs", "v1", credentials=get_credentials())

    try:
        document_id = create_document(service, args.title)
        insert_text(service, document_id, args.text)
    except HttpError as e:
        sys.exit(f"✗ ドキュメントの作成に失敗しました（{e.status_code}: {e.reason}）")

    print(f"✓ 「{args.title}」を作成し、{len(args.text)} 文字を挿入しました")
    print(f"    ID  : {document_id}")
    print(f"    URL : https://docs.google.com/document/d/{document_id}/edit")


if __name__ == "__main__":
    main()
