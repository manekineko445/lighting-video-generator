"""
app.py – Streamlit UI (precise progress)
"""
import streamlit as st, pathlib, tempfile, os
from video_generator import generate_video

st.set_page_config(page_title="照明動画ジェネレータ", layout="centered")
st.title("🎞️ 照明動画ジェネレータ")

excel_file = st.file_uploader("📄 照明案 (xlsx)", type="xlsx")
audio_file = st.file_uploader("🎵 音源", type=("mp3","wav","m4a","aac","flac","ogg"))
run = st.button("▶ 生成", disabled=not (excel_file and audio_file))

st.divider()

if run:
    bar = st.progress(0, text="アップロード中…")
    status = st.empty()

    # テンポラリ保存
    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as ex_tmp,\
         tempfile.NamedTemporaryFile(delete=False, suffix=pathlib.Path(audio_file.name).suffix) as au_tmp:
        ex_tmp.write(excel_file.getbuffer())
        au_tmp.write(audio_file.getbuffer())

    def _update(p):
        bar.progress(p, text=f"生成中… {p}%")

    try:
        status.info("🔧 動画生成を開始しました")
        mp4 = generate_video(
            pathlib.Path(ex_tmp.name),
            pathlib.Path(au_tmp.name),
            progress_callback=_update,
            sheet_title=pathlib.Path(excel_file.name).stem
        )
        status.success("✅ 完了！")
        bar.progress(100, text="完了！ 100%")
        st.video(mp4)
        with open(mp4,"rb") as fp:
            st.download_button("📥 ダウンロード", fp.read(),
                               file_name=f"{pathlib.Path(excel_file.name).stem}.mp4",
                               mime="video/mp4", use_container_width=True)
    except Exception as e:
        bar.empty()
        status.error(f"❌ 失敗: {e}")
    finally:
        for p in (ex_tmp.name, au_tmp.name):
            try: os.remove(p)
            except: pass
