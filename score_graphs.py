import csv
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # 画面に出さず画像ファイルとして保存する
import matplotlib.pyplot as plt
import openpyxl

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_FILE = BASE_DIR / "4-2-2-3.xlsx"
OUTPUT_DIR = BASE_DIR / "graphs"

# 色覚の多様性に配慮して検証済みの配色（この順番で使う）
COLORS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
SURFACE = "#fcfcfb"
TEXT = "#0b0b0b"
TEXT_SUB = "#52514e"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"

plt.rcParams.update({
    "font.family": ["Yu Gothic", "Meiryo", "sans-serif"],
    "font.size": 11,
    "figure.facecolor": SURFACE,
    "axes.facecolor": SURFACE,
    "axes.edgecolor": AXIS,
    "axes.labelcolor": TEXT_SUB,
    "axes.titlesize": 15,
    "axes.titleweight": "bold",
    "axes.titlecolor": TEXT,
    "axes.titlepad": 14,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "xtick.color": TEXT_SUB,
    "ytick.color": TEXT_SUB,
    "legend.frameon": False,
    "savefig.dpi": 150,
    "savefig.bbox": "tight",
})


def load_data(path):
    """名前・所属・スコアの一覧を読み込む（Excel と CSV のどちらにも対応）"""
    if path.suffix.lower() == ".csv":
        with open(path, encoding="utf-8-sig", newline="") as f:
            rows = list(csv.reader(f))
    else:
        ws = openpyxl.load_workbook(path, data_only=True).active
        rows = [list(r) for r in ws.iter_rows(values_only=True)]

    header = [str(h).strip() for h in rows[0]]
    name_col, dept_col, score_col = (header.index(h) for h in ("名前", "所属", "スコア"))

    data = []
    for row in rows[1:]:
        try:
            data.append((row[name_col], row[dept_col], float(row[score_col])))
        except (TypeError, ValueError, IndexError):
            continue  # 空行や数値でないスコアは飛ばす
    return data


def group_by_dept(data):
    groups = {}
    for _, dept, score in data:
        groups.setdefault(dept, []).append(score)
    # 人数の多い順に並べる（色はこの順番で固定して全グラフで共通にする）
    return dict(sorted(groups.items(), key=lambda g: len(g[1]), reverse=True))


def pie_chart(groups, path):
    depts = list(groups)
    counts = [len(groups[d]) for d in depts]
    total = sum(counts)

    fig, ax = plt.subplots(figsize=(7, 6))
    wedges, _, autotexts = ax.pie(
        counts,
        labels=[f"{d}\n{c}人" for d, c in zip(depts, counts)],
        colors=COLORS[: len(depts)],
        autopct="%1.1f%%",
        startangle=90,
        counterclock=False,
        pctdistance=0.72,
        labeldistance=1.12,
        wedgeprops={"edgecolor": SURFACE, "linewidth": 2},
        textprops={"color": TEXT, "fontsize": 12},
    )
    for t in autotexts:
        t.set_fontweight("bold")
    ax.set_title(f"所属ごとの参加者数（全{total}人）")
    ax.legend(wedges, depts, title="所属", loc="center left", bbox_to_anchor=(1.02, 0.5))
    ax.axis("equal")
    fig.savefig(path)
    plt.close(fig)


def bar_chart(groups, path):
    depts = list(groups)
    measures = [
        ("平均点", [sum(s) / len(s) for s in groups.values()]),
        ("最高点", [max(s) for s in groups.values()]),
        ("最低点", [min(s) for s in groups.values()]),
    ]

    fig, ax = plt.subplots(figsize=(9, 5.5))
    width = 0.26
    for i, (label, values) in enumerate(measures):
        xs = [x + (i - 1) * width for x in range(len(depts))]
        bars = ax.bar(xs, values, width, label=label, color=COLORS[i],
                      edgecolor=SURFACE, linewidth=2, zorder=2)
        ax.bar_label(bars, labels=[f"{v:.1f}" if i == 0 else f"{v:.0f}" for v in values],
                     padding=3, fontsize=9, color=TEXT_SUB)

    ax.set_xticks(range(len(depts)), depts, fontsize=12)
    ax.set_ylim(0, 105)
    ax.set_xlabel("所属")
    ax.set_ylabel("スコア（点）")
    ax.set_title("所属ごとのスコア（平均点・最高点・最低点）")
    ax.yaxis.grid(True, color=GRID, linewidth=1, zorder=0)
    ax.tick_params(axis="x", length=0)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.12), ncol=3)
    fig.savefig(path)
    plt.close(fig)


def histogram(data, path):
    scores = [s for _, _, s in data]
    mean = sum(scores) / len(scores)

    # 5点きざみのビン（例: 70～74点、75～79点 …）にして、点数帯ごとの人数を見やすくする
    low = int(min(scores) // 5 * 5)
    high = int(max(scores) // 5 * 5 + 5)
    bins = list(range(low, high + 1, 5))

    fig, ax = plt.subplots(figsize=(9, 5.5))
    counts, _, patches = ax.hist(scores, bins=bins, color=COLORS[0],
                                 edgecolor=SURFACE, linewidth=2, zorder=2, label="人数")
    ax.bar_label(patches, labels=[f"{int(c)}人" for c in counts], padding=3, color=TEXT_SUB)
    ax.axvline(mean, color=TEXT, linestyle="--", linewidth=1.5, zorder=3,
               label=f"平均 {mean:.1f}点")

    ax.set_xticks(bins)
    ax.set_ylim(0, max(counts) * 1.18)
    ax.set_xlabel("スコア（点）　※各区間は左端を含み右端を含まない（例: 70～74点）")
    ax.set_ylabel("人数（人）")
    ax.set_title(f"全参加者のスコア分布（{len(scores)}人・5点きざみ）")
    ax.yaxis.grid(True, color=GRID, linewidth=1, zorder=0)
    ax.legend(loc="upper left")
    fig.savefig(path)
    plt.close(fig)


def main():
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_FILE
    data = load_data(path)
    groups = group_by_dept(data)
    OUTPUT_DIR.mkdir(exist_ok=True)

    outputs = [
        ("円グラフ", OUTPUT_DIR / "pie_chart.png", lambda p: pie_chart(groups, p)),
        ("棒グラフ", OUTPUT_DIR / "bar_chart.png", lambda p: bar_chart(groups, p)),
        ("ヒストグラム", OUTPUT_DIR / "histogram.png", lambda p: histogram(data, p)),
    ]

    print(f"{path.name} から {len(data)} 人分のデータを読み込みました。")
    for label, out, draw in outputs:
        draw(out)
        print(f"  {label}を保存しました: {out.relative_to(BASE_DIR)}")


if __name__ == "__main__":
    main()
