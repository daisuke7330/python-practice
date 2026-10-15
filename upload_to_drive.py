"""ローカルのファイルを Google ドライブにアップロードする

使い方:
    python upload_to_drive.py ファイル1 [ファイル2 ...] [--folder フォルダID]

ファイルを指定せずに実行すると、アップロードするファイルのパスを聞かれる。
初回はブラウザが開くので、Google アカウントでログインして許可する。
"""

import argparse
import mimetypes
import sys
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

BASE_DIR = Path(__file__).resolve().parent
CREDENTIALS_FILE = BASE_DIR / "credentials.json"  # Google Cloud で作った OAuth クライアントの鍵
TOKEN_FILE = BASE_DIR / "token.json"  # 2回目以降ログインを省略するための保存ファイル

# このアプリがアップロードしたファイルだけを扱える権限（ドライブ全体には触れない）
SCOPES = ["https://www.googleapis.com/auth/drive.file"]


def get_credentials():
    creds = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    else:
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


def upload(service, path, folder_id=None):
    mime_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    metadata = {"name": path.name}
    if folder_id:
        metadata["parents"] = [folder_id]

    # resumable=True にすると大きいファイルも分割して送れる
    media = MediaFileUpload(str(path), mimetype=mime_type, resumable=True)
    return service.files().create(
        body=metadata, media_body=media, fields="id, name, size, webViewLink"
    ).execute()


def parse_args():
    parser = argparse.ArgumentParser(description="ファイルを Google ドライブにアップロードします。")
    parser.add_argument("files", nargs="*", help="アップロードするファイルのパス")
    parser.add_argument("--folder", help="アップロード先のフォルダ ID（省略するとマイドライブ直下）")
    args = parser.parse_args()

    if not args.files:
        # 実行ボタンから起動したときは引数がないので、ここで聞く
        text = input("アップロードするファイルのパスを入力してください: ").strip().strip('"')
        args.files = [text] if text else []
    return args


def main():
    args = parse_args()
    paths = [Path(f) for f in args.files]
    if not paths:
        sys.exit("ファイルが指定されていません。")

    missing = [p for p in paths if not p.is_file()]
    if missing:
        sys.exit("エラー: 次のファイルが見つかりません。\n" + "\n".join(f"  {p}" for p in missing))

    service = build("drive", "v3", credentials=get_credentials())

    failed = 0
    for path in paths:
        try:
            result = upload(service, path, args.folder)
        except HttpError as e:
            failed += 1
            print(f"✗ {path.name}: アップロードに失敗しました（{e.status_code}: {e.reason}）")
            continue
        size_kb = int(result.get("size", 0)) / 1024
        print(f"✓ {result['name']}（{size_kb:,.1f} KB）をアップロードしました")
        print(f"    ID  : {result['id']}")
        print(f"    URL : {result['webViewLink']}")

    print(f"\n完了: 成功 {len(paths) - failed} 件 / 失敗 {failed} 件")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
