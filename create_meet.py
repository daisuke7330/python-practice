"""Google Meet のミーティングを新しく作り、参加リンクを表示する

使い方:
    python create_meet.py [--access open|trusted|restricted]

引数なしで実行すると、組織の設定どおりの参加条件でミーティングを作る。
upload_to_drive.py と同じ credentials.json を使い、ログイン情報は token_meet.json に保存する。
初回はブラウザが開くので、Google アカウントでログインして許可する。
"""

import argparse
import sys
from pathlib import Path

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

BASE_DIR = Path(__file__).resolve().parent
CREDENTIALS_FILE = BASE_DIR / "credentials.json"  # Google Cloud で作った OAuth クライアントの鍵
TOKEN_FILE = BASE_DIR / "token_meet.json"  # Meet 用のログイン保存ファイル（ドライブ用とは権限が違うので分ける）

# このアプリが作ったミーティングだけを扱える権限
SCOPES = ["https://www.googleapis.com/auth/meetings.space.created"]

# 誰がノックなしで参加できるか
ACCESS_TYPES = {
    "open": "OPEN",  # リンクを知っていれば誰でも
    "trusted": "TRUSTED",  # 同じ組織の人と招待された人
    "restricted": "RESTRICTED",  # 招待された人だけ
}


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


def create_space(service, access=None):
    # Meet では会議室にあたるものを「スペース」と呼ぶ。作ると参加リンクが付いてくる
    body = {"config": {"accessType": ACCESS_TYPES[access]}} if access else {}
    return service.spaces().create(body=body).execute()


def parse_args():
    parser = argparse.ArgumentParser(description="Google Meet のミーティングを作成し、参加リンクを表示します。")
    parser.add_argument(
        "--access",
        choices=ACCESS_TYPES,
        help="参加できる人（open=誰でも / trusted=組織内と招待者 / restricted=招待者のみ）",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    service = build("meet", "v2", credentials=get_credentials())

    try:
        space = create_space(service, args.access)
    except HttpError as e:
        sys.exit(f"✗ ミーティングの作成に失敗しました（{e.status_code}: {e.reason}）")

    print("✓ ミーティングを作成しました")
    print(f"    参加リンク     : {space['meetingUri']}")
    print(f"    ミーティングコード: {space['meetingCode']}")
    print(f"    スペース名     : {space['name']}")


if __name__ == "__main__":
    main()
