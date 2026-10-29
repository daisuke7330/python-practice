"""4. Outlook：メールを「下書き」フォルダに保存する（送信はしない）

デスクトップ版 Outlook（クラシック）を COM で操作する。Outlook が起動していなくても動く。
"""

import win32com.client


def save_draft(mail, attachments=()):
    outlook = win32com.client.Dispatch("Outlook.Application")
    item = outlook.CreateItem(0)   # 0 = メール
    item.To = ";".join(mail["to"])
    item.CC = ";".join(mail["cc"])
    item.Subject = mail["subject"]
    item.Body = mail["body"]
    for path in attachments:
        item.Attachments.Add(str(path))
    item.Save()   # 下書きに保存するだけ。Send() は呼ばない
    return item.Subject, item.Recipients.Count, item.Attachments.Count
