# 照明動画ジェネレータ

## 概要
Excelの照明案と音源ファイルをもとに、カウントダウン付きの照明タイミング動画を自動で作成するツールです。

## 使い方

1. `app.py` を実行します（`start_app.bat` をダブルクリックでもOK）。
2. 「照明案.xlsx」と「音源ファイル.mp3」をアップロード。
3. 「生成」ボタンを押すと、照明タイミング付き動画（.mp4）が作られます。

## 注意
- フォントは Windows の `meiryob.ttc` を使っています（環境に合わせて変更してください）。
- Python 3.11 以上 + `moviepy`, `Pillow`, `pandas` などが必要です。

## 必須ライブラリ
```bash
pip install -r requirements.txt
