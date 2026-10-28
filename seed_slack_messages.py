"""要約テスト用の会話（架空）を Slack のチャンネルに流す

使い方:
    python seed_slack_messages.py [--channel チャンネル]

slack_to_line_summary.py の動作確認用。架空のネットショップのチームが、
年末セールの準備について話している会話を、複数の人の名前で投稿する。
Slack アプリに chat:write.customize の権限が必要（投稿者名を変えるため）。
"""

import argparse
import time

from post_slack import load_config, post_message

# 架空のチームの会話（名前・数字はすべて作り物）
MESSAGES = [
    ("山本（店長）", ":man_office_worker:", "おはようございます。今日は年末セールの準備について決めたいので、昼までに意見ください。"),
    ("佐藤（仕入れ）", ":package:", "在庫の確認しました。人気のマグカップ3種は合計420個あります。ただ、黒の大きいサイズだけ残り35個なので、セールで出すとすぐ切れそうです。"),
    ("鈴木（デザイン）", ":art:", "バナーはたたき台できてます。「最大30%OFF」で作りましたが、割引率は確定ですか？"),
    ("山本（店長）", ":man_office_worker:", "割引率は 20%で確定にします。30%だと利益が残らないので。鈴木さん、バナーを20%に直してください。"),
    ("鈴木（デザイン）", ":art:", "了解です。20%版を12/3（水）までに出します。"),
    ("佐藤（仕入れ）", ":package:", "黒の大きいサイズは追加で100個発注できます。ただ、メーカーの締め切りが12/1（月）の17時です。"),
    ("山本（店長）", ":man_office_worker:", "追加発注はお願いします。黒田さん、12/1の17時までに発注書を作って佐藤さんに回してもらえますか？"),
    ("黒田（運営）", ":memo:", "承知しました。12/1の15時までには回します。"),
    ("高橋（CS）", ":headphones:", "ちなみに、去年のセールでは配送遅れの問い合わせが1日50件くらい来ました。今年は発送までの日数を商品ページに書いておきたいです。"),
    ("山本（店長）", ":man_office_worker:", "それは大事。発送目安は「ご注文から3営業日以内」で統一しましょう。高橋さん、問い合わせ用の返信テンプレートも用意をお願いします。"),
    ("高橋（CS）", ":headphones:", "テンプレートは12/5（金）までに作ります。"),
    ("鈴木（デザイン）", ":art:", "ところで、昨日の社内ランチのカレー美味しかったですね笑"),
    ("佐藤（仕入れ）", ":package:", "辛さちょうどよかったです！"),
    ("山本（店長）", ":man_office_worker:", "では整理します。セール期間は 12/10（水）〜12/14（日）、割引は20%。黒田さんはセール開始前日の12/9に、商品ページの価格と在庫数を最終チェックしてください。"),
    ("黒田（運営）", ":memo:", "了解です。12/9に価格と在庫の最終チェックをします。"),
    ("山本（店長）", ":man_office_worker:", "注意点として、黒の大きいサイズは追加分が届くのが12/8の予定なので、遅れたらすぐ共有してください。みなさんよろしくお願いします！"),
]


def parse_args():
    parser = argparse.ArgumentParser(description="要約テスト用の会話（架空）を Slack に投稿します。")
    parser.add_argument("--channel", help="投稿先のチャンネル（省略時: slack_config.json の channel）")
    return parser.parse_args()


def main():
    args = parse_args()
    config = load_config()
    channel = args.channel or config.get("channel")
    for name, icon, text in MESSAGES:
        post_message(config["bot_token"], channel, text, username=name, icon_emoji=icon)
        print(f"✓ {name}: {text[:30]}…")
        time.sleep(1.2)  # Slack の投稿は1秒に1回程度まで
    print(f"\n{len(MESSAGES)} 件を {channel} に投稿しました。")


if __name__ == "__main__":
    main()
