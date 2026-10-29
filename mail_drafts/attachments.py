"""3. 添付：フォルダの中から、名前の型に合う一番新しいファイルを探す

例：デスクトップの「掲載予定_*.xlsx」のうち、更新日時が一番新しいもの。
"""

from pathlib import Path


def latest_file(folder, pattern):
    files = [p for p in Path(folder).expanduser().glob(pattern) if p.is_file() and not p.name.startswith("~$")]
    return max(files, key=lambda p: p.stat().st_mtime) if files else None
