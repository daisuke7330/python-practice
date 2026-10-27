"""Gmail で指定した宛先にメールを送る

使い方:
    python send_gmail.py [--to 宛先] [--subject 件名] [--body 本文]

宛先を指定せずに実行すると、ログインした自分のアドレスに送る（動作確認用）。
upload_to_drive.py と同じ credentials.json を使い、ログイン情報は token_gmail.json に保存する。
初回はブラウザが開くので、Google アカウントでログインして許可する。
"""

import argparse
import base64
import sys
from datetime import datetime
from email.mime.text import MIMEText
from pathlib import Path

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import AuthorizedSession, Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

BASE_DIR = Path(__file__).resolve().parent
CREDENTIALS_FILE = BASE_DIR / "credentials.json"  # Google Cloud で作った OAuth クライアントの鍵
TOKEN_FILE = BASE_DIR / "token_gmail.json"  # Gmail 用のログイン保存ファイル（ほかの API とは権限が違うので分ける）

# メールの送信だけできる権限と、宛先省略時に自分のアドレスを調べるための権限
SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/userinfo.email",
    "openid",
]


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


def get_my_address(creds):
    res = AuthorizedSession(creds).get("https://www.googleapis.com/oauth2/v2/userinfo")
    res.raise_for_status()
    return res.json()["email"]


def build_message(to, subject, body):
    # Gmail API には、メール全体を base64url で符号化した文字列で渡す
    message = MIMEText(body, "plain", "utf-8")
    message["To"] = to
    message["Subject"] = subject
    return {"raw": base64.urlsafe_b64encode(message.as_bytes()).decode()}


def parse_args():
    parser = argparse.ArgumentParser(description="Gmail で指定した宛先にメールを送ります。")
    parser.add_argument("--to", help="宛先メールアドレス（省略時: ログインした自分のアドレス）")
    parser.add_argument("--subject", default="Gmail API からのテスト送信", help="件名")
    parser.add_argument("--body", help="本文（省略時: 送信日時入りのテスト文）")
    return parser.parse_args()


def main():
    args = parse_args()
    creds = get_credentials()
    service = build("gmail", "v1", credentials=creds)

    to = args.to or get_my_address(creds)
    sent_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    body = args.body or f"このメールは Python から Gmail API を使って送信しました。\n送信日時: {sent_at}"

    try:
        sent = service.users().messages().send(userId="me", body=build_message(to, args.subject, body)).execute()
    except HttpError as e:
        sys.exit(f"✗ メールの送信に失敗しました（{e.status_code}: {e.reason}）")

    print("✓ メールを送信しました")
    print(f"    宛先       : {to}")
    print(f"    件名       : {args.subject}")
    print(f"    送信日時   : {sent_at}")
    print(f"    メッセージID: {sent['id']}")


if __name__ == "__main__":
    main()
