import streamlit as st
from datetime import datetime

# 앱 제목 설정
st.title("❤️ 우리 가족 파이썬 기록장")

# 앱 실행 동안 데이터를 저장할 공간 만들기
if "posts" not in st.session_state:
    st.session_state.posts = []

# --- 1. 글 작성 구역 ---
st.subheader("📸 새 기록 남기기")
with st.form("upload_form", clear_on_submit=True):
    author = st.selectbox("작성자", ["아빠", "엄마", "첫째", "둘째"])
    photo = st.file_uploader("사진을 선택하세요", type=["png", "jpg", "jpeg"])
    caption = st.text_area("오늘 어떤 일이 있었나요?")
    submitted = st.form_submit_button("가족 기록 올리기")

    # [올리기] 버튼을 눌렀을 때 실행되는 로직
    if submitted:
        if photo is not None and caption.strip() != "":
            new_post = {
                "author": author,
                "photo": photo,
                "caption": caption,
                "date": datetime.now().strftime("%Y년 %m월 %d일 %H:%M")
            }
            # 최신 글이 맨 위에 오도록 추가
            st.session_state.posts.insert(0, new_post)
            st.success("기록이 성공적으로 등록되었습니다!")
        else:
            st.warning("사진과 글을 모두 작성해 주세요.")

st.divider()

# --- 2. 게시물 피드 구역 ---
st.subheader("📖 가족 타임라인")

if not st.session_state.posts:
    st.info("아직 등록된 기록이 없습니다. 위에서 첫 기록을 남겨보세요!")
else:
    for post in st.session_state.posts:
        st.markdown(f"**{post['author']}** · `{post['date']}`")
        st.image(post['photo'], use_container_width=True)
        st.write(post['caption'])
        st.divider()