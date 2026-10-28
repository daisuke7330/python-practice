"""議事録テスト用の会議音声（架空）を Gemini の音声合成で作る

使い方:
    python make_sample_meeting_audio.py [--out ファイル名]

meet_minutes_to_doc.py の動作確認用。Google Meet の録画・録音は有料の Workspace でしか
使えないため、架空の定例会議（2人）の台本を Gemini API で読み上げて WAV ファイルにする。
gemini_config.json の api_key を使う。
"""

import argparse
import base64
import json
import sys
import wave
from pathlib import Path

import requests

BASE_DIR = Path(__file__).resolve().parent
TTS_MODEL = "gemini-3.8-flash-tts"
TTS_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{TTS_MODEL}:generateContent"

# 架空の会議（名前・数字はすべて作り物）
SCRIPT = """山本: お疲れさまです。では、11月の定例会議を始めます。今日は年末セールの準備と、来月のメルマガの2つです。
黒田: よろしくお願いします。まずセールの状況ですが、バナーは鈴木さんが12月3日までに20%オフ版を出してくれる予定です。
山本: ありがとうございます。在庫はどうですか。
黒田: マグカップの黒の大きいサイズが残り35個なので、100個追加で発注します。メーカーの締め切りが12月1日の17時なので、私が当日の15時までに発注書を作ります。
山本: お願いします。届くのはいつ頃ですか。
黒田: 12月8日の予定です。遅れそうな時は、すぐにチャットで共有します。
山本: 了解です。次にメルマガですが、去年はセール初日の朝に送って、開封率が32%でした。今年も初日の朝8時でいきましょう。
黒田: わかりました。原稿は私が作って、12月5日までに山本さんに確認をお願いします。
山本: はい。件名は、送料無料も入れて目立つようにしてください。
黒田: 承知しました。件名の案を3つ出します。
山本: では最後に、次回の定例は12月2日の火曜日、10時からにします。今日はありがとうございました。
黒田: ありがとうございました。"""


def load_api_key():
    path = BASE_DIR / "gemini_config.json"
    if not path.exists():
        sys.exit("エラー: gemini_config.json が見つかりません。")
    key = json.loads(path.read_text(encoding="utf-8-sig")).get("api_key")
    if not key:
        sys.exit("エラー: gemini_config.json に api_key が入っていません。")
    return key


def script_parts():
    # 1行ずつ「誰が話すか」を付けて渡す
    parts = []
    for line in SCRIPT.splitlines():
        speaker, text = line.split(": ", 1)
        parts.append({"text": text, "speechMetadata": {"speaker": speaker}})
    return parts


def synthesize(api_key):
    body = {
        "contents": [{"parts": script_parts()}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {"multiSpeakerVoiceConfig": {"speakerVoiceConfigs": [
                # 話す人ごとに声を変える（2人まで）
                {"speaker": "山本", "voiceConfig": {"prebuiltVoiceConfig": {"voiceName": "Charon"}}},
                {"speaker": "黒田", "voiceConfig": {"prebuiltVoiceConfig": {"voiceName": "Kore"}}},
            ]}},
        },
    }
    res = requests.post(TTS_URL, headers={"x-goog-api-key": api_key}, json=body, timeout=300)
    if res.status_code != 200:
        sys.exit(f"✗ 音声の作成に失敗しました（{res.status_code}: {res.text[:300]}）")
    part = res.json()["candidates"][0]["content"]["parts"][0]["inlineData"]
    return base64.b64decode(part["data"])


def save_wav(path, pcm):
    # Gemini の音声は 24kHz・16bit・モノラルの生データなので、WAV の形に包んで保存する
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(24000)
        w.writeframes(pcm)


def main():
    parser = argparse.ArgumentParser(description="議事録テスト用の会議音声（架空）を作ります。")
    parser.add_argument("--out", default="sample_meeting.wav", help="保存するファイル名（既定: sample_meeting.wav）")
    args = parser.parse_args()

    pcm = synthesize(load_api_key())
    out = BASE_DIR / args.out
    save_wav(out, pcm)
    print(f"✓ 会議音声を作成しました: {out.name}（約 {len(pcm) / 48000:.0f} 秒）")


if __name__ == "__main__":
    main()
