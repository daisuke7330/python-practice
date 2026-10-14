import random
import unicodedata

LOW, HIGH = 1, 100


def main():
    answer = random.randint(LOW, HIGH)
    tries = 0

    print(f"{LOW}～{HIGH} の数字を当ててください！")

    while True:
        # 全角の数字も受け付けるよう半角にそろえる
        text = unicodedata.normalize("NFKC", input("数字を入力: ")).strip()

        if not text.isdigit():
            print("数字を入力してください。")
            continue

        guess = int(text)
        if not LOW <= guess <= HIGH:
            print(f"{LOW}～{HIGH} の範囲で入力してください。")
            continue

        tries += 1
        if guess < answer:
            print("もっと大きい")
        elif guess > answer:
            print("もっと小さい")
        else:
            print(f"正解！ 答えは {answer} でした。{tries} 回で当たりました。")
            break


if __name__ == "__main__":
    main()
