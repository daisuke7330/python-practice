"""2. ひな形：JSON のひな形を読み、日付や追加の文を差し込んでメールの中身を作る

ひな形の例（mail_templates.sample.json）:
  "媒体掲載予定": {"to": [...], "cc": [...], "subject": "媒体掲載予定",
                   "body": "皆様\\n\\nお疲れ様です。\\n…{extra}…\\n\\n{sign}",
                   "attach": {"folder": "~/Desktop", "pattern": "掲載予定_*.xlsx"}}
本文の {extra} には、その週だけ入れたい文（新商品のお知らせなど）が入る。無ければ行ごと消える。
"""

import json
import re
from pathlib import Path


def load_templates(path):
    data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    return {k: v for k, v in data.items() if not k.startswith("_")}   # "_" で始まるキーは説明用


def fill(text, values):
    """{名前} を values の値に置き換える。values に無い {…} はそのまま残す（間違いに気づけるように）"""
    return re.sub(r"\{(\w+)\}", lambda m: str(values[m.group(1)]) if m.group(1) in values else m.group(0), text)


def render(tpl, values, extra=""):
    v = dict(values, extra=extra.strip(), sign=tpl.get("sign", ""))
    body = fill(tpl["body"], v)
    body = re.sub(r"\n{3,}", "\n\n", body)   # {extra} が空だった時の空行を詰める
    left = re.findall(r"\{\w+\}", tpl["subject"] + body)
    return {"to": tpl.get("to", []), "cc": tpl.get("cc", []), "subject": fill(tpl["subject"], v),
            "body": body, "unfilled": [x for x in left if x.strip("{}") not in v]}
