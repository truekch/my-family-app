import streamlit as st
import json
import os
from datetime import datetime
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload, MediaIoBaseDownload
import io

# 앱 기본 설정
st.set_page_config(page_title="우리 가족 파이썬 기록장", page_icon="❤️")
st.title("❤️ 우리 가족 파이썬 기록장")

# --- Google OAuth 2.0 사용자 인증 연동 설정 ---
SCOPES = ['https://www.googleapis.com/auth/drive']

@st.cache_resource
def get_drive_service():
    """Streamlit Secrets의 OAuth 정보를 사용해 내 구글 원 2TB 드라이브 API 서비스 생성"""
    oauth_config = st.secrets["google_oauth"]
    
    creds = Credentials(
        token=None,
        refresh_token=oauth_config["refresh_token"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=oauth_config["client_id"],
        client_secret=oauth_config["client_secret"],
        scopes=SCOPES
    )
    
    # 토큰 자동 갱신
    if not creds.valid:
        creds.refresh(Request())
        
    return build('drive', 'v3', credentials=creds)

try:
    drive_service = get_drive_service()
    FOLDER_ID = st.secrets["DRIVE_FOLDER_ID"]
except Exception as e:
    st.error(f"Google Drive 연결 설정에 실패했습니다: {e}")
    st.stop()

# --- 구글 드라이브 파일 읽기/쓰기 도우미 함수 ---
def upload_file_to_drive(file_bytes, file_name, mime_type):
    """내 구글 원 2TB 드라이브 폴더로 사진 직접 업로드"""
    file_metadata = {
        'name': file_name,
        'parents': [FOLDER_ID]
    }
    fh = io.BytesIO(file_bytes)
    media = MediaIoBaseUpload(fh, mimetype=mime_type, resumable=False)
    
    uploaded_file = drive_service.files().create(
        body=file_metadata,
        media_body=media,
        fields='id'
    ).execute()
    
    return uploaded_file.get('id')

def download_file_from_drive(file_id):
    """내 구글 드라이브에서 파일 바이트 데이터 가져오기"""
    request = drive_service.files().get_media(fileId=file_id)
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    return fh.getvalue()

def load_posts_from_drive():
    """내 구글 드라이브에서 posts.json 파일 찾아 게시글 목록 불러오기"""
    try:
        query = f"'{FOLDER_ID}' in parents and name = 'posts.json' and trashed = false"
        results = drive_service.files().list(q=query, fields="files(id)").execute()
        files = results.get('files', [])
        
        if not files:
            return [], None
        
        file_id = files[0]['id']
        content = download_file_from_drive(file_id)
        return json.loads(content.decode('utf-8')), file_id
    except Exception as e:
        st.error(f"게시글 로딩 중 오류가 발생했습니다: {e}")
        return [], None

def save_posts_to_drive(posts, existing_file_id=None):
    """게시글 목록을 json으로 변환하여 내 구글 드라이브에 저장"""
    json_bytes = json.dumps(posts, ensure_ascii=False, indent=2).encode('utf-8')
    fh = io.BytesIO(json_bytes)
    media = MediaIoBaseUpload(fh, mimetype='application/json', resumable=False)
    
    if existing_file_id:
        drive_service.files().update(
            fileId=existing_file_id, media_body=media
        ).execute()
    else:
        file_metadata = {'name': 'posts.json', 'parents': [FOLDER_ID]}
        drive_service.files().create(
            body=file_metadata, media_body=media
        ).execute()

# --- 게시물 데이터 불러오기 ---
posts, posts_file_id = load_posts_from_drive()

# --- 1. 사진 및 글 업로드 폼 ---
st.subheader("📸 새 기록 남기기")
with st.form("upload_form", clear_on_submit=True):
    author = st.selectbox("작성자", ["아빠", "엄마", "첫째", "둘째"])
    photo = st.file_uploader("사진을 선택하세요", type=["jpg", "jpeg", "png", "heic", "webp"])
    caption = st.text_area("오늘 어떤 일이 있었나요?")
    submitted = st.form_submit_button("가족 기록 올리기")

    if submitted:
        if photo is not None and caption.strip() != "":
            with st.spinner("내 구글 원 2TB 드라이브로 사진을 전송 중입니다..."):
                try:
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    photo_name = f"{timestamp}_{photo.name}"
                    mime_type = photo.type if photo.type else 'image/jpeg'
                    
                    # 1. 내 구글 드라이브에 사진 업로드
                    photo_drive_id = upload_file_to_drive(
                        photo.getvalue(), photo_name, mime_type
                    )
                    
                    # 2. 새 포스트 데이터 생성
                    new_post = {
                        "author": author,
                        "photo_id": photo_drive_id,
                        "caption": caption,
                        "date": datetime.now().strftime("%Y년 %m월 %d일 %H:%M")
                    }
                    
                    # 3. 최신 포스트를 맨 앞에 추가 후 내 구글 드라이브에 저장
                    posts.insert(0, new_post)
                    save_posts_to_drive(posts, posts_file_id)
                    
                    st.success("🎉 내 구글 원 2TB 드라이브에 안전하게 영구 저장되었습니다!")
                    st.rerun()
                except Exception as e:
                    st.error(f"사진 업로드 중 오류가 발생했습니다: {e}")
        else:
            st.warning("사진과 글을 모두 입력해 주세요.")

st.divider()

# --- 2. 가족 타임라인 피드 ---
st.subheader("📖 가족 타임라인")

if not posts:
    st.info("아직 등록된 기록이 없습니다. 위에서 첫 번째 가족 추억을 남겨보세요!")
else:
    for post in posts:
        st.markdown(f"**{post['author']}** · `{post['date']}`")
        try:
            # 내 구글 드라이브에서 사진 데이터 가져와서 표시
            img_bytes = download_file_from_drive(post["photo_id"])
            st.image(img_bytes, use_container_width=True)
        except Exception:
            st.warning("🖼️ 사진을 불러오는 중 오류가 발생했습니다.")
        st.write(post["caption"])
        st.divider()
