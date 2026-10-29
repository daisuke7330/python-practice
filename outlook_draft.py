"""毎週の定例メールを、ひな形から Outlook の下書きに作る（送信は人が確認してから）

使い方:
    python outlook_draft.py --list
    python outlook_draft.py 媒体掲載予定 [--extra "今週だけ入れる文"] [--date 2026-10-29] [--dry-run]

毎週「前回のメールを探す → 宛先をコピー → 件名の週を直す → 本文を直す → 最新のファイルを添付」していた作業を自動化する。
  1. 日付（mail_drafts/week.py）       ：件名の「○月第○週」などを計算
  2. ひな形（mail_drafts/template.py）  ：JSON のひな形に日付や追加の文を差し込む
  3. 添付（mail_drafts/attachments.py） ：決まったフォルダから一番新しいファイルを探す
  4. Outlook（mail_drafts/outlook.py）  ：下書きフォルダに保存（Send はしない）
ひな形は mail_templates.json（宛先が入るので GitHub には上げない）。無ければ mail_templates.sample.json を使う。
"""

import argparse
import sys
from datetime import date
from pathlib import Path

from mail_drafts.attachments import latest_file
from mail_drafts.template import load_templates, render
from mail_drafts.week import week_values

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES = BASE_DIR / "mail_templates.json"
SAMPLE = BASE_DIR / "mail_templates.sample.json"


def parse_args():
    p = argparse.ArgumentParser(description="定例メールの Outlook 下書きをひな形から作る")
    p.add_argument("name", nargs="?", help="ひな形の名前（--list で一覧）")
    p.add_argument("--list", action="store_true", help="ひな形の一覧を表示")
    p.add_argument("--extra", default="", help="本文の {extra} に入れる文（\\n で改行）")
    p.add_argument("--date", type=date.fromisoformat, default=date.today(), help="送る日（既定：今日）")
    p.add_argument("--dry-run", action="store_true", help="下書きを作らず、内容を表示するだけ")
    return p.parse_args()


def main():
    args = parse_args()
    path = TEMPLATES if TEMPLATES.exists() else SAMPLE
    templates = load_templates(path)
    if args.list or not args.name:
        print(f"ひな形（{path.name}）: " + " / ".join(templates))
        return
    if args.name not in templates:
        sys.exit(f"エラー: ひな形「{args.name}」がありません。--list で確認してください。")
    tpl = templates[args.name]
    mail = render(tpl, week_values(args.date), args.extra.replace("\\n", "\n"))
    if mail["unfilled"]:
        sys.exit(f"エラー: 埋まっていない項目があります: {', '.join(mail['unfilled'])}")

    files = []
    if tpl.get("attach"):
        found = latest_file(tpl["attach"]["folder"], tpl["attach"]["pattern"])
        if not found:
            sys.exit(f"エラー: 添付ファイルが見つかりません（{tpl['attach']['folder']} / {tpl['attach']['pattern']}）")
        files.append(found)

    print(f"件名: {mail['subject']}")
    print(f"宛先: {len(mail['to'])}件  CC: {len(mail['cc'])}件  添付: {', '.join(f.name for f in files) or 'なし'}")
    print("--- 本文 ---\n" + mail["body"] + "\n------------")
    if args.dry_run:
        print("（--dry-run のため下書きは作っていません）")
        return
    from mail_drafts.outlook import save_draft   # Outlook は下書きを作る時だけ使う
    subject, n_to, n_att = save_draft(mail, files)
    print(f"✓ Outlook の下書きに保存しました：{subject}（宛先 {n_to}件、添付 {n_att}件）。送信はしていません")


if __name__ == "__main__":
    main()
