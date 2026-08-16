import streamlit as st
import json
import os
from datetime import datetime
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload, MediaIoBaseDownload
import io
from PIL import Image

# 앱 기본 설정
st.set_page_config(page_title="우리 가족 파이썬 기록장", page_icon="❤️")

# --- 1. 가족 전용 비밀번호(PIN 6자리) 잠금 화면 ---
FAMILY_PIN = st.secrets.get("FAMILY_PIN", "123456")

if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

if not st.session_state["authenticated"]:
    st.title("🔒 우리 가족 전용 공간")
    st.write("가족 전용 비밀번호(PIN 6자리)를 입력해 주세요.")
    
    with st.form("login_form"):
        pin_input = st.text_input("비밀번호 6자리", type="password", max_chars=6)
        submit_pin = st.form_submit_button("접속하기")
        
        if submit_pin:
            if pin_input == FAMILY_PIN:
                st.session_state["authenticated"] = True
                st.success("확인되었습니다!")
                st.rerun()
            else:
                st.error("비밀번호가 올바르지 않습니다. 다시 입력해 주세요.")
    st.stop()

# --- 2. 인증 완료 후 메인 앱 화면 ---
st.title("❤️ 우리 가족 파이썬 기록장")

col_title, col_logout = st.columns([4, 1])
with col_logout:
    if st.button("🔒 잠그기"):
        st.session_state["authenticated"] = False
        st.rerun()

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
    
    if not creds.valid:
        creds.refresh(Request())
        
    return build('drive', 'v3', credentials=creds)

try:
    drive_service = get_drive_service()
    FOLDER_ID = st.secrets["DRIVE_FOLDER_ID"]
except Exception as e:
    st.error(f"Google Drive 연결 설정에 실패했습니다: {e}")
    st.stop()

# --- 구글 드라이브 파일 읽기/쓰기/삭제 도우미 함수 ---
def upload_file_to_drive(file_bytes, file_name, mime_type):
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
    request = drive_service.files().get_media(fileId=file_id)
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    return fh.getvalue()

def delete_file_from_drive(file_id):
    try:
        drive_service.files().delete(fileId=file_id).execute()
    except Exception:
        pass

def load_posts_from_drive():
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

# --- 3. 사진 및 글 업로드 폼 ---
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
                    
                    photo_drive_id = upload_file_to_drive(
                        photo.getvalue(), photo_name, mime_type
                    )
                    
                    new_post = {
                        "author": author,
                        "photo_id": photo_drive_id,
                        "caption": caption,
                        "date": datetime.now().strftime("%Y년 %m월 %d일 %H:%M")
                    }
                    
                    posts.insert(0, new_post)
                    save_posts_to_drive(posts, posts_file_id)
                    
                    st.success("🎉 내 구글 원 2TB 드라이브에 안전하게 영구 저장되었습니다!")
                    st.rerun()
                except Exception as e:
                    st.error(f"사진 업로드 중 오류가 발생했습니다: {e}")
        else:
            st.warning("사진과 글을 모두 입력해 주세요.")

st.divider()

# --- 4. 가족 타임라인 피드 ---
st.subheader("📖 가족 타임라인")

if not posts:
    st.info("아직 등록된 기록이 없습니다. 위에서 첫 번째 가족 추억을 남겨보세요!")
else:
    for idx, post in enumerate(posts):
        st.markdown(f"**{post['author']}** · `{post['date']}`")
        try:
            # 메모리 Segfault 방지: BytesIO -> PIL Image -> 안전한 width 설정
            img_bytes = download_file_from_drive(post["photo_id"])
            image_obj = Image.open(io.BytesIO(img_bytes))
            st.image(image_obj, width="stretch")
        except Exception:
            st.warning("🖼️ 사진을 불러오는 중 오류가 발생했습니다.")
            
        st.write(post["caption"])
        
        # 고유 ID 생성 (Key 충돌 방지)
        post_key = post.get("photo_id", str(idx))
        
        with st.expander("⚙️ 게시글 관리"):
            # 1. 글 수정
            st.markdown("**:pencil2: 글 수정하기**")
            authors_list = ["아빠", "엄마", "첫째", "둘째"]
            curr_author_idx = authors_list.index(post['author']) if post['author'] in authors_list else 0
            
            edit_author = st.selectbox("작성자 변경", authors_list, index=curr_author_idx, key=f"auth_{post_key}")
            edit_caption = st.text_area("글 내용 수정", value=post["caption"], key=f"cap_{post_key}")
            
            if st.button("수정 저장", key=f"btn_save_{post_key}"):
                posts[idx]["author"] = edit_author
                posts[idx]["caption"] = edit_caption
                save_posts_to_drive(posts, posts_file_id)
                st.success("수정되었습니다!")
                st.rerun()
            
            st.divider()
            
            # 2. 글 삭제
            st.markdown("**:wastebasket: 글 삭제하기**")
            if st.button("🗑️ 게시글 및 사진 영구 삭제", key=f"btn_del_{post_key}"):
                delete_file_from_drive(post["photo_id"])
                posts.pop(idx)
                save_posts_to_drive(posts, posts_file_id)
                st.success("삭제되었습니다!")
                st.rerun()
                    
        st.divider()
