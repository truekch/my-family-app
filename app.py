import streamlit as st
import json
import os
import base64
from datetime import datetime
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload, MediaIoBaseDownload
import io

# 앱 기본 페이지 설정
st.set_page_config(page_title="우리 가족 파이썬 기록장", page_icon="❤️")

# --- 1. 가족 전용 비밀번호(PIN) 인증 ---
FAMILY_PIN = st.secrets.get("FAMILY_PIN", "123456")

if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

if not st.session_state["authenticated"]:
    st.title("🔒 우리 가족 전용 공간")
    st.write("가족 전용 비밀번호(PIN)를 입력해 주세요.")
    
    pin_input = st.text_input("비밀번호 6자리", type="password", key="pin_input_field")
    if st.button("접속하기", key="btn_login"):
        if pin_input == FAMILY_PIN:
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("비밀번호가 올바르지 않습니다.")
    st.stop()

# --- 2. Google OAuth 2.0 및 Drive 서비스 생성 ---
SCOPES = ['https://www.googleapis.com/auth/drive']

@st.cache_resource
def get_drive_service():
    oauth_config = st.secrets["google_oauth"]
    creds = Credentials(
        token=None,
        refresh_token=oauth_config["refresh_token"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=oauth_config["client_id"],
        client_secret=oauth_config["client_secret"],
        scopes=SCOPES
    )
    if not creds.valid:
        creds.refresh(Request())
    return build('drive', 'v3', credentials=creds)

try:
    drive_service = get_drive_service()
    FOLDER_ID = st.secrets["DRIVE_FOLDER_ID"]
except Exception as e:
    st.error(f"Google Drive 연결 실패: {e}")
    st.stop()

# --- 3. 구글 드라이브 캐싱 지원 함수 ---
@st.cache_data(ttl=3600, show_spinner=False)
def download_image_b64(file_id):
    """드라이브에서 이미지를 받아와 Base64로 변환 후 캐싱(1시간)"""
    try:
        request = drive_service.files().get_media(fileId=file_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        img_bytes = fh.getvalue()
        return base64.b64encode(img_bytes).decode('utf-8')
    except Exception:
        return None

def download_file_bytes(file_id):
    request = drive_service.files().get_media(fileId=file_id)
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    return fh.getvalue()

def upload_file_to_drive(file_bytes, file_name, mime_type):
    file_metadata = {'name': file_name, 'parents': [FOLDER_ID]}
    fh = io.BytesIO(file_bytes)
    media = MediaIoBaseUpload(fh, mimetype=mime_type, resumable=False)
    uploaded_file = drive_service.files().create(body=file_metadata, media_body=media, fields='id').execute()
    return uploaded_file.get('id')

def delete_file_from_drive(file_id):
    try:
        drive_service.files().delete(fileId=file_id).execute()
    except Exception:
        pass

def load_posts():
    try:
        query = f"'{FOLDER_ID}' in parents and name = 'posts.json' and trashed = false"
        results = drive_service.files().list(q=query, fields="files(id)").execute()
        files = results.get('files', [])
        if not files:
            return [], None
        file_id = files[0]['id']
        content = download_file_bytes(file_id)
        return json.loads(content.decode('utf-8')), file_id
    except Exception as e:
        st.error(f"데이터 로딩 실패: {e}")
        return [], None

def save_posts(posts, file_id=None):
    json_bytes = json.dumps(posts, ensure_ascii=False, indent=2).encode('utf-8')
    fh = io.BytesIO(json_bytes)
    media = MediaIoBaseUpload(fh, mimetype='application/json', resumable=False)
    if file_id:
        drive_service.files().update(fileId=file_id, media_body=media).execute()
    else:
        file_metadata = {'name': 'posts.json', 'parents': [FOLDER_ID]}
        drive_service.files().create(body=file_metadata, media_body=media).execute()
    st.cache_data.clear() # 게시글 저장 시 캐시 초기화

# --- 4. 메인 화면 구성 ---
col_head1, col_head2 = st.columns([4, 1])
with col_head1:
    st.title("❤️ 우리 가족 파이썬 기록장")
with col_head2:
    if st.button("🔒 잠그기", key="btn_logout"):
        st.session_state["authenticated"] = False
        st.rerun()

posts, posts_file_id = load_posts()

# 📸 새 기록 남기기 폼
st.subheader("📸 새 기록 남기기")
with st.form("upload_form", clear_on_submit=True):
    author = st.selectbox("작성자", ["아빠", "엄마", "첫째", "둘째"])
    photo = st.file_uploader("사진 선택", type=["jpg", "jpeg", "png", "heic", "webp"])
    caption = st.text_area("오늘 어떤 일이 있었나요?")
    submitted = st.form_submit_button("가족 기록 올리기")

    if submitted:
        if photo is not None and caption.strip() != "":
            with st.spinner("내 구글 원 2TB 드라이브로 저장 중..."):
                try:
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    photo_name = f"{timestamp}_{photo.name}"
                    mime_type = photo.type if photo.type else 'image/jpeg'
                    
                    photo_id = upload_file_to_drive(photo.getvalue(), photo_name, mime_type)
                    
                    new_post = {
                        "id": timestamp,
                        "author": author,
                        "photo_id": photo_id,
                        "caption": caption,
                        "date": datetime.now().strftime("%Y년 %m월 %d일 %H:%M")
                    }
                    posts.insert(0, new_post)
                    save_posts(posts, posts_file_id)
                    st.success("🎉 영구 저장되었습니다!")
                    st.rerun()
                except Exception as e:
                    st.error(f"업로드 에러: {e}")
        else:
            st.warning("사진과 글을 모두 입력해 주세요.")

st.divider()

# 📖 가족 타임라인 피드
st.subheader("📖 가족 타임라인")

if not posts:
    st.info("아직 등록된 기록이 없습니다. 첫 번째 추억을 올려보세요!")
else:
    for idx, post in enumerate(posts):
        p_id = post.get("id", str(idx))
        st.markdown(f"**{post['author']}** · `{post['date']}`")
        
        # 캐싱된 이미지 출력
        b64_str = download_image_b64(post["photo_id"])
        if b64_str:
            st.markdown(f'<img src="data:image/jpeg;base64,{b64_str}" style="width:100%; border-radius:8px; margin-bottom:10px;">', unsafe_allow_html=True)
        else:
            st.warning("🖼️ 사진을 불러올 수 없습니다.")
            
        st.write(post["caption"])
        
        # 삭제 버튼만 깔끔하게 배치 (메모리 부담 최소화)
        if st.button("🗑️ 삭제", key=f"del_{p_id}_{idx}"):
            delete_file_from_drive(post["photo_id"])
            posts.pop(idx)
            save_posts(posts, posts_file_id)
            st.success("삭제되었습니다!")
            st.rerun()
            
        st.divider()
