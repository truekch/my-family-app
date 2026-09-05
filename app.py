import streamlit as st
import json
import io
import time
import copy
from datetime import datetime
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload, MediaIoBaseDownload
from googleapiclient.errors import HttpError

# 앱 기본 페이지 설정
st.set_page_config(page_title="우리 가족 파이썬 기록장", page_icon="❤️", layout="centered")

# --- 🎨 모바일 최적화 & 타이틀 한줄 정렬 및 글씨 크기 개선 CSS ---
st.markdown("""
<style>
* {
    -webkit-tap-highlight-color: transparent;
}
html {
    scroll-behavior: smooth;
}
@media (max-width: 640px) {
    h1 {
        font-size: 26px !important;
        white-space: nowrap !important;
    }
    h3 {
        font-size: 19px !important;
        white-space: nowrap !important;
    }
    div[data-testid="stHorizontalBlock"] {
        flex-direction: row !important;
        flex-wrap: nowrap !important;
        gap: 8px !important;
    }
    div[data-testid="stColumn"] {
        min-width: 0 !important;
    }
}
div[data-testid="stButton"] button {
    padding: 4px 8px !important;
    min-height: 42px !important;
    white-space: nowrap !important;
    word-break: keep-all !important;
    color: #1a202c !important;
}
div[data-testid="stButton"] button p {
    white-space: nowrap !important;
    word-break: keep-all !important;
    font-size: 16px !important;
    font-weight: bold !important;
    color: #1a202c !important;
}
.scroll-to-top {
    position: fixed !important;
    bottom: 25px !important;
    left: 20px !important;
    width: 44px !important;
    height: 44px !important;
    background-color: #4A5568 !important;
    color: white !important;
    border-radius: 50% !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    font-size: 20px !important;
    font-weight: bold !important;
    text-decoration: none !important;
    z-index: 99999 !important;
    box-shadow: 0 4px 10px rgba(0, 0, 0, 0.3) !important;
}

/* --- 사진 확대(Lightbox) 스타일 --- */
details.lightbox-details summary {
    list-style: none !important;
    cursor: pointer;
}
details.lightbox-details summary::-webkit-details-marker {
    display: none !important;
}
.lightbox-overlay {
    display: none;
}
details.lightbox-details[open] .lightbox-overlay {
    display: flex !important;
    position: fixed !important;
    top: 0 !important;
    left: 0 !important;
    width: 100vw !important;
    height: 100vh !important;
    background: rgba(0, 0, 0, 0.92) !important;
    z-index: 999999 !important;
    align-items: center !important;
    justify-content: center !important;
}
details.lightbox-details[open] .lightbox-overlay img {
    max-width: 95vw !important;
    max-height: 95vh !important;
    object-fit: contain !important;
}
</style>
""", unsafe_allow_html=True)

# --- 🎨 로그인 화면 버튼 크기 세분화 스타일링 ---
if "authenticated" not in st.session_state or not st.session_state["authenticated"]:
    st.markdown("""
    <style>
    /* 이름 선택 버튼 (40px, 정사각형) */
    div[data-testid="stHorizontalBlock"] div[data-testid="stColumn"] div[data-testid="stButton"] button {
        aspect-ratio: 1 / 1 !important;
        width: 100% !important;
        border-radius: 20px !important;
        font-size: 40px !important;
        font-weight: bold !important;
        background-color: #ffffff !important;
        border: 2px solid #e2e8f0 !important;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05) !important;
        transition: all 0.2s ease !important;
        color: #1a202c !important;
    }
    div[data-testid="stHorizontalBlock"] div[data-testid="stColumn"] div[data-testid="stButton"] button p {
        font-size: 40px !important;
        font-weight: bold !important;
        color: #1a202c !important;
    }
    
    /* 비밀번호 입력 화면의 '입장하기', '← 이름 다시 선택' 버튼 (32px로 조정) */
    div[data-testid="stTextInput"] ~ div div[data-testid="stButton"] button,
    div[data-testid="stTextInput"] ~ div div[data-testid="stHorizontalBlock"] div[data-testid="stColumn"] div[data-testid="stButton"] button {
        aspect-ratio: auto !important;
        font-size: 32px !important;
    }
    div[data-testid="stTextInput"] ~ div div[data-testid="stButton"] button p,
    div[data-testid="stTextInput"] ~ div div[data-testid="stHorizontalBlock"] div[data-testid="stColumn"] div[data-testid="stButton"] button p {
        font-size: 32px !important;
    }

    div[data-testid="stHorizontalBlock"] div[data-testid="stColumn"] div[data-testid="stButton"] button:hover {
        border-color: #3182ce !important;
        background-color: #ebf8ff !important;
        transform: translateY(-2px);
    }
    </style>
    """, unsafe_allow_html=True)

st.markdown('<a href="#timeline_anchor" class="scroll-to-top">▲</a>', unsafe_allow_html=True)

FAMILY_MEMBERS = ["창협", "지원", "채영", "서영"]
FAMILY_PIN = st.secrets.get("FAMILY_PIN", "123456")

# --- 세션 상태 초기화 ---
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False
if "current_author" not in st.session_state:
    st.session_state["current_author"] = None
if "login_author" not in st.session_state:
    st.session_state["login_author"] = None

# --- 1. 가족 전용 바둑판식 로그인 화면 ---
if not st.session_state["authenticated"]:
    st.title("🔒 우리 가족 전용 공간")
    
    # 1단계: 가족 이름 선택 (2x2 정사각형 바둑판 버튼)
    if not st.session_state["login_author"]:
        st.markdown("### 👋 기록을 남길 분을 선택해 주세요")
        st.write("")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🐵\n\n창협", use_container_width=True, key="btn_member_0"):
                st.session_state["login_author"] = FAMILY_MEMBERS[0]
                st.rerun()
        with col2:
            if st.button("🐶\n\n지원", use_container_width=True, key="btn_member_1"):
                st.session_state["login_author"] = FAMILY_MEMBERS[1]
                st.rerun()
                
        st.write("")
        col3, col4 = st.columns(2)
        with col3:
            if st.button("🐲\n\n채영", use_container_width=True, key="btn_member_2"):
                st.session_state["login_author"] = FAMILY_MEMBERS[2]
                st.rerun()
        with col4:
            if st.button("🐴\n\n서영", use_container_width=True, key="btn_member_3"):
                st.session_state["login_author"] = FAMILY_MEMBERS[3]
                st.rerun()
        st.stop()
    
    # 2단계: PIN 번호 입력
    else:
        selected_name = st.session_state["login_author"]
        st.markdown(f"### ✨ **{selected_name}** 님, 환영합니다!")
        st.write("가족 전용 비밀번호 6자리를 입력해 주세요.")
        
        pin_input = st.text_input("비밀번호", type="password", key="pin_input_field")
        
        col_login, col_back = st.columns(2)
        with col_login:
            if st.button("입장하기", use_container_width=True, key="btn_do_login"):
                if pin_input == FAMILY_PIN:
                    st.session_state["authenticated"] = True
                    st.session_state["current_author"] = selected_name
                    st.session_state["login_author"] = None
                    st.rerun()
                else:
                    st.error("비밀번호가 올바르지 않습니다.")
        with col_back:
            if st.button("← 이름 다시 선택", use_container_width=True, key="btn_back_name"):
                st.session_state["login_author"] = None
                st.rerun()
        st.stop()

# --- 2. Google OAuth 2.0 및 Drive 서비스 생성 ---
SCOPES = ['https://www.googleapis.com/auth/drive']

@st.cache_resource(show_spinner=False)
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
    st.error(f"Google Drive 연결 초기화 실패: {e}")
    st.stop()

# --- 3. [핵심 방어] 구글 API 병목 차단용 백오프 재시도 로직 ---
def execute_with_retry(func, retries=5): 
    delay = 1
    for i in range(retries):
        try:
            return func()
        except HttpError as err:
            if err.resp.status in [403, 429, 500, 502, 503, 504] and i < retries - 1:
                time.sleep(delay)
                delay *= 2
                continue
            raise err
        except Exception as e:
            if i < retries - 1:
                time.sleep(delay)
                delay *= 2
                continue
            raise e

def upload_file_to_drive(file_bytes, file_name, mime_type):
    def _upload():
        file_metadata = {'name': file_name, 'parents': [FOLDER_ID]}
        fh = io.BytesIO(file_bytes)
        media = MediaIoBaseUpload(fh, mimetype=mime_type, resumable=False)
        res = drive_service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        fh.close()
        
        try:
            drive_service.permissions().create(
                fileId=res.get('id'),
                body={'type': 'anyone', 'role': 'reader'}
            ).execute()
        except Exception:
            pass
            
        return res
    
    res = execute_with_retry(_upload)
    return res.get('id')

def delete_file_from_drive(file_id):
    if not file_id:
        return
    try:
        execute_with_retry(lambda: drive_service.files().delete(fileId=file_id).execute())
    except Exception:
        pass

def download_file_bytes(file_id):
    def _download():
        request = drive_service.files().get_media(fileId=file_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        val = fh.getvalue()
        fh.close()
        return val
    return execute_with_retry(_download)

# --- [핵심 방어] 데이터 강력 캐싱 ---
@st.cache_data(ttl=60, show_spinner=False)
def load_posts():
    try:
        def _list_files():
            query = f"'{FOLDER_ID}' in parents and name = 'posts.json' and trashed = false"
            return drive_service.files().list(q=query, fields="files(id)").execute()
        
        results = execute_with_retry(_list_files)
        files = results.get('files', [])
        if not files:
            return [], None
        file_id = files[0]['id']
        content = download_file_bytes(file_id)
        return json.loads(content.decode('utf-8')), file_id
    except Exception:
        return [], None

def save_posts(posts_data, file_id=None):
    json_bytes = json.dumps(posts_data, ensure_ascii=False, indent=2).encode('utf-8')
    
    def _save():
        fh = io.BytesIO(json_bytes)
        media = MediaIoBaseUpload(fh, mimetype='application/json', resumable=False)
        target_id = file_id
        if not target_id:
            query = f"'{FOLDER_ID}' in parents and name = 'posts.json' and trashed = false"
            results = drive_service.files().list(q=query, fields="files(id)").execute()
            files = results.get('files', [])
            if files:
                target_id = files[0]['id']

        if target_id:
            drive_service.files().update(fileId=target_id, media_body=media).execute()
        else:
            file_metadata = {'name': 'posts.json', 'parents': [FOLDER_ID]}
            drive_service.files().create(body=file_metadata, media_body=media).execute()
        fh.close()

    execute_with_retry(_save)
    load_posts.clear()

# --- 4. 메인 화면 ---
posts, posts_file_id = load_posts()

if "show_upload_form" not in st.session_state:
    st.session_state["show_upload_form"] = False

current_user = st.session_state.get("current_author", "가족")

col_top_left, col_top_right = st.columns([3, 1])
with col_top_left:
    if st.button("📸 새 기록 남기기", key="toggle_upload_btn", use_container_width=True):
        st.session_state["show_upload_form"] = not st.session_state["show_upload_form"]
with col_top_right:
    if st.button(f"👤 {current_user} (나가기)", key="btn_logout", use_container_width=True):
        st.session_state["authenticated"] = False
        st.session_state["current_author"] = None
        st.rerun()

if st.session_state["show_upload_form"]:
    with st.form("upload_form", clear_on_submit=True):
        st.subheader(f"✏️ {current_user} 님의 새로운 추억 남기기")
        photos = st.file_uploader("사진 선택 (여러 장 가능)", type=["jpg", "jpeg", "png", "webp"], accept_multiple_files=True)
        caption = st.text_area("오늘 어떤 일이 있었나요?")
        submitted = st.form_submit_button("가족 기록 올리기")

        if submitted:
            if caption.strip() != "":
                with st.spinner("구글 드라이브로 저장 중..."):
                    try:
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        photo_ids = []
                        
                        if photos:
                            for p_idx, photo in enumerate(photos):
                                photo_name = f"{timestamp}_{p_idx}_{photo.name}"
                                mime_type = photo.type if photo.type else 'image/jpeg'
                                p_id = upload_file_to_drive(photo.getvalue(), photo_name, mime_type)
                                photo_ids.append(p_id)
                        
                        new_post = {
                            "id": timestamp,
                            "author": current_user,
                            "photo_ids": photo_ids,
                            "caption": caption,
                            "date": datetime.now().strftime("%Y년 %m월 %d일 %H:%M"),
                            "comments": []
                        }
                        
                        updated_posts = copy.deepcopy(posts)
                        updated_posts.insert(0, new_post)
                        save_posts(updated_posts, posts_file_id)
                        
                        st.session_state["show_upload_form"] = False
                        st.success("🎉 저장되었습니다!")
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        st.error(f"업로드 에러: {e}")
            else:
                st.warning("글 내용을 작성해 주세요.")

st.divider()

st.markdown('<div id="timeline_anchor" style="position:relative; top:-100px; height:0px;"></div>', unsafe_allow_html=True)
st.subheader("📖 우리 가족 타임라인")

search_col1, search_col2 = st.columns([1, 2])
with search_col1:
    filter_author = st.selectbox("👤 작성자 필터", ["전체"] + FAMILY_MEMBERS, key="filter_author")
with search_col2:
    search_keyword = st.text_input("🔍 글 내용 검색어", placeholder="찾고 싶은 키워드 입력...", key="search_keyword")

filtered_posts = [
    p for p in posts 
    if (filter_author == "전체" or p["author"] == filter_author) and 
       (not search_keyword.strip() or search_keyword.strip().lower() in p["caption"].lower())
]

if not filtered_posts:
    st.info("기록이 없습니다.")
else:
    for idx, post in enumerate(filtered_posts):
        p_id = post.get("id", str(idx))
        p_ids = post.get("photo_ids", [])

        if f"pop_key_{p_id}" not in st.session_state:
            st.session_state[f"pop_key_{p_id}"] = 0
        pop_key = st.session_state[f"pop_key_{p_id}"]

        col_info, col_menu = st.columns([5, 1])
        with col_info:
            st.markdown(f"**{post['author']}** · `{post['date']}`")
        
        with col_menu:
            with st.popover("⋮", key=f"popover_{p_id}_{pop_key}"):
                if st.button("🗑️ 삭제하기", key=f"pop_btn_del_{p_id}_{pop_key}", use_container_width=True):
                    st.session_state[f"mode_{p_id}"] = "delete" if st.session_state.get(f"mode_{p_id}") != "delete" else None
                    st.session_state[f"pop_key_{p_id}"] += 1
                    st.rerun()

        if st.session_state.get(f"mode_{p_id}") == "delete":
            with st.status("⚠️ 기록 삭제 확인", expanded=True):
                st.write("정말로 이 기록을 삭제하시겠습니까?")
                col_del_yes, col_del_no = st.columns(2)
                with col_del_yes:
                    if st.button("네, 삭제합니다", type="primary", key=f"confirm_del_btn_{p_id}", use_container_width=True):
                        for img_id in p_ids:
                            delete_file_from_drive(img_id)
                        updated_posts = [p for p in posts if p.get("id") != post.get("id")]
                        save_posts(updated_posts, posts_file_id)
                        st.session_state[f"mode_{p_id}"] = None
                        st.session_state[f"pop_key_{p_id}"] += 1
                        st.rerun()
                with col_del_no:
                    if st.button("취소", key=f"cancel_del_btn_{p_id}", use_container_width=True):
                        st.session_state[f"mode_{p_id}"] = None
                        st.session_state[f"pop_key_{p_id}"] += 1
                        st.rerun()

        # 🖼️ 구글 드라이브 이미지 출력
        if p_ids:
            cols = st.columns(min(len(p_ids), 2))
            for img_idx, img_id in enumerate(p_ids):
                img_url = f"https://lh3.googleusercontent.com/d/{img_id}"
                with cols[img_idx % 2]:
                    st.markdown(f'''
                    <details class="lightbox-details">
                        <summary>
                            <img src="{img_url}" loading="lazy" onerror="this.onerror=null;this.src='https://via.placeholder.com/400x300?text=Image+Loading+Error';" style="width:100%; border-radius:8px; margin-bottom:10px; object-fit:cover; max-height:300px;">
                            <div class="lightbox-overlay">
                                <img src="{img_url}">
                            </div>
                        </summary>
                    </details>
                    ''', unsafe_allow_html=True)

        st.write(post["caption"])

        # 💬 댓글 영역
        comments = post.get("comments", [])
        with st.expander(f"💬 댓글 ({len(comments)}개)"):
            for c in comments:
                st.markdown(f"**{c['author']}** (`{c['date']}`): {c['text']}")
            
            with st.form(f"comment_form_{p_id}", clear_on_submit=True):
                st.markdown(f"💬 **{current_user}** 님 이름으로 댓글 남기기")
                c_text = st.text_input("댓글 내용 입력...", key=f"c_text_{p_id}")
                if st.form_submit_button("댓글 등록"):
                    if c_text.strip():
                        updated_posts = copy.deepcopy(posts)
                        for original_post in updated_posts:
                            if original_post.get("id") == post.get("id"):
                                if "comments" not in original_post:
                                    original_post["comments"] = []
                                original_post["comments"].append({
                                    "author": current_user,
                                    "text": c_text,
                                    "date": datetime.now().strftime("%m/%d %H:%M")
                                })
                                break
                        save_posts(updated_posts, posts_file_id)
                        st.rerun()
        
        st.divider()
