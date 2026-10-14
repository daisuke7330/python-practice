import sys
import unicodedata

import openpyxl

DEFAULT_FILE = r"C:\Users\kikaku9\Desktop\4-2-2-2.xlsx"


def width(text):
    # 全角文字は2マス分として数える（表の列をそろえるため）
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in text)


def pad(text, size, align="left"):
    space = " " * (size - width(text))
    return text + space if align == "left" else space + text


def load_scores(path):
    ws = openpyxl.load_workbook(path, data_only=True).active
    rows = ws.iter_rows(values_only=True)
    header = list(next(rows))
    name_col, subject_col, score_col = (header.index(h) for h in ("名前", "科目", "スコア"))

    scores = {}
    for row in rows:
        name, subject, score = row[name_col], row[subject_col], row[score_col]
        if name is None or not isinstance(score, (int, float)):
            continue
        scores.setdefault(name, []).append((score, subject))
    return scores


def print_table(headers, rows, aligns):
    sizes = [max(width(str(r[i])) for r in [headers] + rows) for i in range(len(headers))]
    line = "+" + "+".join("-" * (s + 2) for s in sizes) + "+"

    def fmt(cells):
        return "| " + " | ".join(pad(str(c), s, a) for c, s, a in zip(cells, sizes, aligns)) + " |"

    print(line)
    print(fmt(headers))
    print(line.replace("-", "="))
    for r in rows:
        print(fmt(r))
    print(line)


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_FILE
    scores = load_scores(path)

    stats = []
    for name, items in scores.items():
        values = [s for s, _ in items]
        high = max(items)
        low = min(items)
        stats.append((name, len(values), sum(values) / len(values), high, low))

    # 平均点の高い順に並べる
    stats.sort(key=lambda s: s[2], reverse=True)

    rows = [
        [f"{rank}位", name, f"{count}件", f"{avg:.1f}", f"{hi[0]}（{hi[1]}）", f"{lo[0]}（{lo[1]}）"]
        for rank, (name, count, avg, hi, lo) in enumerate(stats, 1)
    ]

    print(f"\n■ 参加者別スコア集計（{path}）\n")
    print_table(
        ["順位", "名前", "件数", "平均", "最高点（科目）", "最低点（科目）"],
        rows,
        ["right", "left", "right", "right", "right", "right"],
    )

    all_values = [s for items in scores.values() for s, _ in items]
    print(f"\n  参加者 {len(scores)} 人 / 全 {len(all_values)} 件")
    print(f"  全体平均 {sum(all_values) / len(all_values):.1f} 点"
          f"（最高 {max(all_values)} 点・最低 {min(all_values)} 点）\n")


if __name__ == "__main__":
    main()
