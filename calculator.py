import re
import sys
import unicodedata

NUMBER = r"[+-]?(?:\d+\.?\d*|\.\d+)"
PATTERN = re.compile(rf"^({NUMBER})([+\-*/])({NUMBER})$")


def calculate(expression):
    # 全角の数字・記号やスペースを半角にそろえる
    text = unicodedata.normalize("NFKC", expression)
    text = text.replace("×", "*").replace("÷", "/").replace(" ", "")

    match = PATTERN.match(text)
    if not match:
        return "エラー: 「5+3」のように「数値 演算子 数値」の形で入力してください。"

    a, op, b = float(match[1]), match[2], float(match[3])

    if op == "+":
        result = a + b
    elif op == "-":
        result = a - b
    elif op == "*":
        result = a * b
    elif b == 0:
        return "エラー: 0 で割ることはできません。"
    else:
        result = a / b

    if result.is_integer():
        result = int(result)
    return f"結果: {a:g} {op} {b:g} = {result}"


if len(sys.argv) > 1:
    # 例: python calculator.py 5+3
    print(calculate(" ".join(sys.argv[1:])))
else:
    print(calculate(input("計算式を入力してください (例: 5+3): ")))
