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
from PIL import Image, ImageOps

# 앱 기본 페이지 설정
st.set_page_config(page_title="우리 가족 파이썬 기록장", page_icon="❤️")

# --- 🎨 모바일 최적화, 맨 위로 이동 버튼 & 순수 HTML <details> 라이트박스 CSS ---
st.markdown("""
<style>
/* 1. 모바일에서 컬럼 가로 배치 유지 및 간격 조절 */
@media (max-width: 640px) {
    div[data-testid="stHorizontalBlock"] {
        flex-direction: row !important;
        flex-wrap: nowrap !important;
        gap: 6px !important;
    }
    div[data-testid="stColumn"] {
        min-width: 0 !important;
    }
}

/* 2. 상단 버튼 및 메뉴 버튼 기본 여백 최적화 */
div[data-testid="stButton"] button {
    padding: 4px 8px !important;
    min-height: 36px !important;
    white-space: nowrap !important;
    word-break: keep-all !important;
}

div[data-testid="stButton"] button p {
    white-space: nowrap !important;
    word-break: keep-all !important;
    font-size: 13px !important;
}

/* 3. 좌측 하단 맨 위로 이동(▲) 플로팅 버튼 */
.scroll-to-top {
    position: fixed !important;
    bottom: 25px !important;
    left: 20px !important;
    width: 44px !important;
    height: 44px !important;
    background-color: #4A5568 !important;
    color: white !important;
    border-radius: 50% !important;
    text-align: center !important;
    line-height: 44px !important;
    font-size: 20px !important;
    font-weight: bold !important;
    text-decoration: none !important;
    z-index: 99999 !important;
    box-shadow: 0 4px 10px rgba(0, 0, 0, 0.3) !important;
    transition: background-color 0.2s ease !important;
}
.scroll-to-top:hover {
    background-color: #2D3748 !important;
}

/* 4. 순수 HTML <details> 터치 열기/닫기 라이트박스 */
details.lightbox-details {
    display: block;
}

details.lightbox-details summary {
    list-style: none !important;
    cursor: pointer;
}

details.lightbox-details summary::-webkit-details-marker {
    display: none !important;
}

details.lightbox-details .lightbox-overlay {
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
    border-radius: 6px;
}
</style>
""", unsafe_allow_html=True)

# 페이지 최상단 앵커 & 좌측 하단 맨 위로 이동 플로팅 버튼
st.markdown('<div id="top"></div>', unsafe_allow_html=True)
st.markdown('<a href="#top" class="scroll-to-top">▲</a>', unsafe_allow_html=True)

FAMILY_MEMBERS = ["창협", "지원", "채영", "서영"]

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

# --- 3. 구글 드라이브 캐싱 & EXIF 자동 회전 보정 함수 ---
@st.cache_data(ttl=3600, show_spinner=False)
def download_image_b64(file_id):
    """드라이브에서 이미지를 받아와 EXIF 자동 회전 보정 후 Base64로 변환하여 캐싱(1시간)"""
    if not file_id:
        return None
    try:
        request = drive_service.files().get_media(fileId=file_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        img_bytes = fh.getvalue()
        
        # 📸 EXIF orientation 회전 자동 보정 처리
        img = Image.open(io.BytesIO(img_bytes))
        img = ImageOps.exif_transpose(img)
        
        buffered = io.BytesIO()
        img.save(buffered, format="JPEG")
        return base64.b64encode(buffered.getvalue()).decode('utf-8')
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
    if not file_id:
        return
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
    st.cache_data.clear()

# --- 🗑️ 삭제 확인 모달 다이얼로그 ---
@st.dialog("⚠️ 기록 삭제 확인")
def confirm_delete_dialog(post_id, photo_ids):
    st.write("정말로 이 기록을 삭제하시겠습니까?")
    st.caption("삭제된 글과 사진은 복구할 수 없습니다.")
    col_yes, col_no = st.columns(2)
    with col_yes:
        if st.button("네, 삭제합니다", type="primary", key=f"real_del_{post_id}", use_container_width=True):
            for img_id in photo_ids:
                delete_file_from_drive(img_id)
            global posts
            posts = [p for p in posts if p.get("id") != post_id]
            save_posts(posts, posts_file_id)
            st.session_state[f"confirm_del_{post_id}"] = False
            st.success("삭제되었습니다!")
            st.rerun()
    with col_no:
        if st.button("취소", key=f"cancel_del_{post_id}", use_container_width=True):
            st.session_state[f"confirm_del_{post_id}"] = False
            st.rerun()

# --- 4. 메인 화면 상단 영역 ---
posts, posts_file_id = load_posts()

if "show_upload_form" not in st.session_state:
    st.session_state["show_upload_form"] = False

# 📸 새 기록 남기기 & 🔒 잠그기 버튼 상단 나란히 배치
col_top_left, col_top_right = st.columns([3, 1])
with col_top_left:
    if st.button("📸 새 기록 남기기", key="toggle_upload_btn", use_container_width=True):
        st.session_state["show_upload_form"] = not st.session_state["show_upload_form"]
with col_top_right:
    if st.button("🔒 잠그기", key="btn_logout", use_container_width=True):
        st.session_state["authenticated"] = False
        st.rerun()

# 📸 새 기록 남기기 작성 폼 (토글)
if st.session_state["show_upload_form"]:
    with st.form("upload_form", clear_on_submit=True):
        st.subheader("✏️ 새로운 추억 남기기")
        author = st.selectbox("작성자", FAMILY_MEMBERS)
        photos = st.file_uploader("사진 선택 (여러 장 가능, 선택 사항)", type=["jpg", "jpeg", "png", "heic", "webp"], accept_multiple_files=True)
        caption = st.text_area("오늘 어떤 일이 있었나요?")
        submitted = st.form_submit_button("가족 기록 올리기")

        if submitted:
            if caption.strip() != "":
                with st.spinner("내 구글 원 2TB 드라이브로 저장 중..."):
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
                            "author": author,
                            "photo_ids": photo_ids,
                            "caption": caption,
                            "date": datetime.now().strftime("%Y년 %m월 %d일 %H:%M"),
                            "comments": []
                        }
                        posts.insert(0, new_post)
                        save_posts(posts, posts_file_id)
                        st.session_state["show_upload_form"] = False
                        st.success("🎉 영구 저장되었습니다!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"업로드 에러: {e}")
            else:
                st.warning("글 내용을 작성해 주세요.")

st.divider()

# 📖 우리 가족 타임라인 피드 & 🔍 검색 필터 영역
st.subheader("📖 우리 가족 타임라인")

search_col1, search_col2 = st.columns([1, 2])
with search_col1:
    filter_author = st.selectbox("👤 작성자 필터", ["전체"] + FAMILY_MEMBERS, key="filter_author")
with search_col2:
    search_keyword = st.text_input("🔍 글 내용 검색어", placeholder="찾고 싶은 키워드 입력...", key="search_keyword")

filtered_posts = []
for post in posts:
    author_match = (filter_author == "전체") or (post["author"] == filter_author)
    keyword_match = (not search_keyword.strip()) or (search_keyword.strip().lower() in post["caption"].lower())
    
    if author_match and keyword_match:
        filtered_posts.append(post)

if filter_author != "전체" or search_keyword.strip():
    st.caption(f"🔎 검색 결과: 총 **{len(filtered_posts)}개**의 기록을 찾았습니다.")

if not filtered_posts:
    if not posts:
        st.info("아직 등록된 기록이 없습니다. 상단의 [📸 새 기록 남기기] 버튼을 눌러 첫 추억을 작성해 보세요!")
    else:
        st.info("조건에 일치하는 기록이 없습니다.")
else:
    for idx, post in enumerate(filtered_posts):
        p_id = post.get("id", str(idx))
        p_ids = post.get("photo_ids", [])
        if not p_ids and post.get("photo_id"):
            p_ids = [post.get("photo_id")]

        # 👤 작성자 정보와 우측 상단 ⋮ (점 3개) 드롭다운 메뉴
        col_info, col_menu = st.columns([5, 1])
        with col_info:
            st.markdown(f"**{post['author']}** · `{post['date']}`")
        with col_menu:
            with st.popover("⋮"):
                show_edit = st.button("✏️ 수정하기", key=f"btn_show_edit_{p_id}_{idx}", use_container_width=True)
                if st.button("🗑️ 삭제하기", key=f"del_{p_id}_{idx}", use_container_width=True):
                    st.session_state[f"confirm_del_{p_id}"] = True

        # 🗑️ 삭제 확인 모달 호출
        if st.session_state.get(f"confirm_del_{p_id}", False):
            confirm_delete_dialog(post.get("id"), p_ids)

        # 📸 순수 HTML <details> 기반 터치 확대/축소 이미지 출력
        if p_ids:
            if len(p_ids) == 1:
                b64_str = download_image_b64(p_ids[0])
                if b64_str:
                    st.markdown(f'''
                    <details class="lightbox-details">
                        <summary>
                            <img src="data:image/jpeg;base64,{b64_str}" style="width:100%; border-radius:8px; margin-bottom:10px;">
                            <div class="lightbox-overlay">
                                <img src="data:image/jpeg;base64,{b64_str}">
                            </div>
                        </summary>
                    </details>
                    ''', unsafe_allow_html=True)
            else:
                cols = st.columns(2)
                for img_idx, img_id in enumerate(p_ids):
                    b64_str = download_image_b64(img_id)
                    if b64_str:
                        with cols[img_idx % 2]:
                            st.markdown(f'''
                            <details class="lightbox-details">
                                <summary>
                                    <img src="data:image/jpeg;base64,{b64_str}" style="width:100%; border-radius:8px; margin-bottom:10px;">
                                    <div class="lightbox-overlay">
                                        <img src="data:image/jpeg;base64,{b64_str}">
                                    </div>
                                </summary>
                            </details>
                            ''', unsafe_allow_html=True)

        st.write(post["caption"])

        # ✏️ 수정 화면 toggling
        if f"editing_{p_id}" not in st.session_state:
            st.session_state[f"editing_{p_id}"] = False

        if show_edit:
            st.session_state[f"editing_{p_id}"] = not st.session_state[f"editing_{p_id}"]

        if st.session_state[f"editing_{p_id}"]:
            with st.container():
                st.markdown("---")
                st.markdown("**:pencil2: 게시글 수정**")
                
                curr_author_idx = FAMILY_MEMBERS.index(post['author']) if post['author'] in FAMILY_MEMBERS else 0
                new_author = st.selectbox("작성자", FAMILY_MEMBERS, index=curr_author_idx, key=f"edit_auth_{p_id}")
                new_caption = st.text_area("글 내용", value=post["caption"], key=f"edit_cap_{p_id}")
                
                if st.button("수정 저장하기", key=f"save_edit_{p_id}"):
                    for original_post in posts:
                        if original_post.get("id") == post.get("id"):
                            original_post["author"] = new_author
                            original_post["caption"] = new_caption
                            break
                    save_posts(posts, posts_file_id)
                    st.session_state[f"editing_{p_id}"] = False
                    st.success("수정 완료!")
                    st.rerun()

        # 💬 댓글 영역
        comments = post.get("comments", [])
        with st.expander(f"💬 댓글 ({len(comments)}개)"):
            if comments:
                for c in comments:
                    st.markdown(f"**{c['author']}** (`{c['date']}`)")
                    st.write(c['text'])
                    st.markdown("---")
            else:
                st.caption("아직 댓글이 없습니다. 첫 번째 댓글을 남겨보세요!")
            
            with st.form(f"comment_form_{p_id}", clear_on_submit=True):
                c_author = st.selectbox("댓글 작성자", FAMILY_MEMBERS, key=f"c_auth_{p_id}")
                c_text = st.text_input("댓글 내용을 입력하세요", key=f"c_text_{p_id}")
                c_submit = st.form_submit_button("댓글 남기기")
                
                if c_submit:
                    if c_text.strip() != "":
                        new_comment = {
                            "author": c_author,
                            "text": c_text,
                            "date": datetime.now().strftime("%m/%d %H:%M")
                        }
                        for original_post in posts:
                            if original_post.get("id") == post.get("id"):
                                if "comments" not in original_post:
                                    original_post["comments"] = []
                                original_post["comments"].append(new_comment)
                                break
                        save_posts(posts, posts_file_id)
                        st.success("댓글이 등록되었습니다!")
                        st.rerun()
                    else:
                        st.warning("댓글 내용을 입력해 주세요.")
            
        st.divider()
