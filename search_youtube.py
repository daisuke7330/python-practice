"""YouTube でキーワード検索し、動画のタイトルと URL を表示する

使い方:
    python search_youtube.py [--query キーワード] [--max 件数]

キーワードを指定せずに実行すると「Python 入門」で検索する。
upload_to_drive.py と同じ credentials.json を使い、ログイン情報は token_youtube.json に保存する。
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
TOKEN_FILE = BASE_DIR / "token_youtube.json"  # YouTube 用のログイン保存ファイル（ほかの API とは権限が違うので分ける）

# YouTube の情報を見るだけの権限（動画の投稿や削除はできない）
SCOPES = ["https://www.googleapis.com/auth/youtube.readonly"]

VIDEO_URL = "https://www.youtube.com/watch?v={}"


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


def search_videos(service, query, max_results):
    # type=video で、チャンネルや再生リストを除いて動画だけを探す
    res = service.search().list(
        q=query,
        part="snippet",
        type="video",
        maxResults=max_results,
        regionCode="JP",
        relevanceLanguage="ja",
    ).execute()
    return [(item["snippet"]["title"], VIDEO_URL.format(item["id"]["videoId"])) for item in res.get("items", [])]


def parse_args():
    parser = argparse.ArgumentParser(description="YouTube でキーワード検索し、動画のタイトルと URL を表示します。")
    parser.add_argument("--query", default="Python 入門", help="検索キーワード（省略時: Python 入門）")
    parser.add_argument("--max", type=int, default=5, choices=range(1, 51), metavar="1-50", help="表示する件数（省略時: 5）")
    return parser.parse_args()


def main():
    args = parse_args()
    service = build("youtube", "v3", credentials=get_credentials())

    try:
        videos = search_videos(service, args.query, args.max)
    except HttpError as e:
        sys.exit(f"✗ 検索に失敗しました（{e.status_code}: {e.reason}）")

    if not videos:
        print(f"「{args.query}」に一致する動画は見つかりませんでした。")
        return

    print(f"✓ 「{args.query}」の検索結果（{len(videos)} 件）")
    for i, (title, url) in enumerate(videos, 1):
        print(f"{i}. {title}")
        print(f"   {url}")


if __name__ == "__main__":
    main()
