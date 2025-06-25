"""
video_generator.py
────────────────────────────────────────────────────────────────────────────
Excel の照明キュー + 音源 から
『5 秒カウントダウン → 音源ぴったり尺』の MP4 を生成するワンファイル

✔ D=分 / F=秒 / P=色  … 列番号は定数で変更可
✔ ヘッダー行は SKIP_ROWS でスキップ
✔ カウントダウン後に音源スタート（映像長 = 音源長 + CD）
✔ MoviePy 1.x / 2.x どちらでも動作（AudioArrayClip を後方互換実装）
✔ Streamlit 側の progress_callback(0-100) に 1 秒ごと送信
"""

# === 依存ライブラリ ========================================================
from moviepy.editor import VideoClip, AudioFileClip, CompositeAudioClip
try:                                   # MoviePy 2.x 系
    from moviepy.audio.AudioClip import AudioArrayClip
except ImportError:                    # MoviePy 1.x 系：簡易実装
    import numpy as np
    from moviepy.audio.AudioClip import AudioClip
    def AudioArrayClip(arr, fps):
        dur = len(arr) / fps
        return AudioClip(lambda t: 0.0, fps=fps,
                         duration=dur).set_duration(dur)

from moviepy.video.io.ffmpeg_writer import FFMPEG_VideoWriter
from PIL import Image, ImageDraw, ImageFont
import numpy as np, pandas as pd, pathlib, tempfile, re, os, math
# ==========================================================================

# ---------- ユーザー設定 ----------------------------------------------------
FONT_PATH     = r"C:\Windows\Fonts\meiryob.ttc"   # ← お好みのフォント
COUNTDOWN_SEC = 5                                 # カウントダウン秒
SKIP_ROWS     = 17                                # ヘッダー行数
MIN_COL, SEC_COL, COLOR_COL = 3, 5, 15            # D / F / P 列番号
SIZE          = (1280, 720)                       # 動画サイズ
FPS           = 24                                # フレームレート
# ---------------------------------------------------------------------------

font_big = ImageFont.truetype(FONT_PATH, 100)
font_mid = ImageFont.truetype(FONT_PATH, 50)

# ───────── 文字描画ヘルパ ──────────────────
def draw_center(d, txt, y, f):
    w = d.textbbox((0, 0), txt, font=f)[2]
    d.text(((SIZE[0]-w)//2, y), txt, font=f, fill="white")

def draw_center_x(d, txt, cx, y, f):
    w = d.textlength(txt, font=f)
    d.text((cx-w/2, y), txt, font=f, fill="white")

# ───────── メイン関数 ───────────────────────
def generate_video(
        excel_path: pathlib.Path,
        audio_path: pathlib.Path,
        *,
        progress_callback=lambda p: None,
        sheet_title: str | None = None
    ) -> str:

    # ① Excel 取り込み ------------------------------------------------------
    df = pd.read_excel(excel_path, header=None, skiprows=SKIP_ROWS)
    df = df[[MIN_COL, SEC_COL, COLOR_COL]].rename(
            columns={MIN_COL:'min', SEC_COL:'sec', COLOR_COL:'color'})

    df['min'] = pd.to_numeric(df['min'], errors='coerce').fillna(0)
    df = df[pd.to_numeric(df['sec'], errors='coerce').notna()]
    df['sec']   = df['sec'].astype(float)
    df['start'] = df['min']*60 + df['sec']
    df = df.dropna(subset=['color']).sort_values('start')
    entries = df[['start', 'color']].to_dict('records')
    if not entries:
        raise ValueError('照明キューが 1 件も見つかりません…')

    if sheet_title is None:
        sheet_title = re.split(r'_?照明案', excel_path.stem)[0]

    # ② 音源読み込み（映像尺 = 音源尺 + カウントダウン） ------------------
    audio_raw  = AudioFileClip(str(audio_path))
    audio_len  = audio_raw.duration
    duration   = audio_len + COUNTDOWN_SEC          # ← 映像長を音源基準に

    # ③ フレーム描画 --------------------------------------------------------
    def frame(t):
        cur  = t
        vis  = abs(cur) if cur < 0 else cur
        mm, ss = divmod(vis, 60)
        timer  = f"{int(mm):02d}:{int(ss):02d}.{int((vis-int(vis))*100):02d}"

        nxt = next((e for e in entries if cur < e['start']),
                   {'color':'終了', 'start':cur})
        remain = max(nxt['start'] - cur, 0)

        now = (next((e for e in reversed(entries) if cur >= e['start']),
                    {'color':''}) if cur >= 0 else {'color':''})

        img = Image.new('RGB', SIZE, 'black'); d = ImageDraw.Draw(img)
        draw_center(d, sheet_title, 30,  font_mid)
        draw_center(d, timer,       140, font_big)

        L, R = 300, SIZE[0]-300
        draw_center_x(d, "今",       L, 400, font_mid)
        if cur >= entries[0]['start']:
            draw_center_x(d, now['color'], L, 490, font_mid)

        draw_center_x(d, "次の色",   R, 400, font_mid)
        draw_center_x(d, nxt['color'], R, 490, font_mid)

        draw_center_x(d, f"次の色まで: {math.ceil(remain)}s",
                      SIZE[0]//2, SIZE[1]-120, font_mid)
        return np.asarray(img)

    video = VideoClip(lambda t: frame(t-COUNTDOWN_SEC), duration=duration)

    # ④ 無音 5 秒 + 音源 を AAC で仮出力 -----------------------------------
    rate = 44100
    silence = np.zeros((int(rate*COUNTDOWN_SEC), 1), dtype=np.float32)
    silent_clip = AudioArrayClip(silence, fps=rate)
    audio_trim  = audio_raw.set_start(COUNTDOWN_SEC)   # 5 秒後に開始

    comp_audio = CompositeAudioClip([silent_clip, audio_trim])\
                 .set_duration(duration)

    audio_tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".m4a").name
    comp_audio.write_audiofile(
            audio_tmp,
            fps=rate,
            codec="aac",
            bitrate="192k",
            verbose=False,
            logger=None
    )

    # ⑤ 手動エンコード + 進捗コールバック ----------------------------------
    tmp_mp4 = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4").name
    total_frames = int(duration * FPS)
    writer = FFMPEG_VideoWriter(
                tmp_mp4, SIZE, FPS,
                codec='libx264',
                audiofile=audio_tmp,
                ffmpeg_params=['-pix_fmt', 'yuv420p'],
                preset='medium'
            )

    for i, frm in enumerate(video.iter_frames(fps=FPS, dtype="uint8")):
        writer.write_frame(frm)
        if i % FPS == 0:                       # 1 秒ごとに進捗通知
            progress_callback(int(i/total_frames*100))
    writer.close(); progress_callback(100)

    os.remove(audio_tmp)
    return tmp_mp4


# ---------- 単体テスト用 ----------------------------------------------------
if __name__ == "__main__":
    base   = pathlib.Path(".")
    excel  = next(base.glob("*_照明案.xlsx"))
    stem   = excel.stem.split("_照明案")[0]
    audio  = next(base.glob(f"{stem}*_音源.*"))

    print(f"▶ Excel : {excel.name}")
    print(f"▶ Audio : {audio.name}")
    print("▶▶ 動画を生成します…")
    out = generate_video(excel, audio,
                         progress_callback=lambda p: print(f"\r進捗 {p:3d}%", end=""))
    print(f"\n✅ 完了 → {out}")
