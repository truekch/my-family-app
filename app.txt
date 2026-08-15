import streamlit as st
import json
import os
from datetime import datetime

# 앱 제목 설정
st.title("❤️ 우리 가족 파이썬 기록장")

# --- 데이터 저장 폴더 및 파일 설정 ---
DATA_FILE = "posts.json"
UPLOAD_DIR = "uploads"

# 사진 저장할 폴더가 없으면 새로 생성
if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

# 파일에서 기록 불러오기 함수
def load_posts():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

# 파일에 기록 저장하기 함수
def save_posts(posts):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(posts, f, ensure_ascii=False, indent=2)

# 앱 실행 시 저장된 게시물 불러오기
posts = load_posts()

# --- 1. 글 작성 구역 ---
st.subheader("📸 새 기록 남기기")
with st.form("upload_form", clear_on_submit=True):
    author = st.selectbox("작성자", ["아빠", "엄마", "첫째", "둘째"])
    photo = st.file_uploader("사진을 선택하세요 (모든 이미지 형식 가능)")
    caption = st.text_area("오늘 어떤 일이 있었나요?")
    submitted = st.form_submit_button("가족 기록 올리기")

    if submitted:
        if photo is not None and caption.strip() != "":
            # 파일 이름 중복 방지를 위해 현재 시간으로 이름 생성
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            photo_filename = f"{timestamp}_{photo.name}"
            photo_path = os.path.join(UPLOAD_DIR, photo_filename)

            # 사진을 uploads 폴더에 실제로 저장
            with open(photo_path, "wb") as f:
                f.write(photo.getbuffer())

            # 새 게시물 정보 작성
            new_post = {
                "author": author,
                "photo_path": photo_path,
                "caption": caption,
                "date": datetime.now().strftime("%Y년 %m월 %d일 %H:%M")
            }
            # 최신 글이 제일 위에 오도록 추가 후 파일 저장
            posts.insert(0, new_post)
            save_posts(posts)
            st.success("기록이 성공적으로 영구 저장되었습니다!")
            st.rerun()
        else:
            st.warning("사진과 글을 모두 작성해 주세요.")

st.divider()

# --- 2. 게시물 피드 구역 ---
st.subheader("📖 가족 타임라인")

if not posts:
    st.info("아직 등록된 기록이 없습니다. 위에서 첫 기록을 남겨보세요!")
else:
    for post in posts:
        st.markdown(f"**{post['author']}** · `{post['date']}`")
        if os.path.exists(post["photo_path"]):
            st.image(post["photo_path"], use_container_width=True)
        else:
            st.warning("사진 파일을 찾을 수 없습니다.")
        st.write(post["caption"])
        st.divider()