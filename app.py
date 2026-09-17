import streamlit as st
import time
import datetime
import re
import os
import json

# 모듈 임포트
from config import (
    NAVER_API_KEY_ID, NAVER_API_KEY, GEMINI_API_KEY, SEARCH_KEYWORD,
    TOSS_ACCESS_KEY, TOSS_SECRET_KEY, TOSS_PUBLISHER_ID,
    TOSS_PRODUCT_COUNT, TOSS_ENABLED,
)
from modules.news_fetcher import fetch_latest_news
from modules.content_extractor import extract_contents_from_news_items
from modules.synthesizer import synthesize_blog_post
from modules.toss_shopping import append_toss_footer, fetch_best_selling

# 페이지 설정 (와이드 모드로 변경)
st.set_page_config(page_title="AutoBlog Web", page_icon="📝", layout="wide")

# 세션 상태(보관함) 초기화
if 'history' not in st.session_state:
    st.session_state.history = []

# 사이드바 설정 (Streamlit Secrets > 사이드바 입력 > .env 순으로 유효)
with st.sidebar:
    st.header("⚙️ 설정 (Settings)")

    st.subheader("🔑 네이버 / Gemini API")
    st.caption("입력칸에 넣으면 바로 적용됩니다 (새로고침하면 초기화, 영구 저장은 아래 Secrets 참고).")
    naver_id_in = st.text_input("NAVER_API_KEY_ID", value=NAVER_API_KEY_ID or "", type="password")
    naver_key_in = st.text_input("NAVER_API_KEY", value=NAVER_API_KEY or "", type="password")
    gemini_in = st.text_input("GEMINI_API_KEY", value=GEMINI_API_KEY or "", type="password")

    # 유효 키 = 사이드바 입력 우선, 비어 있으면 Secrets/.env 값 사용
    eff_naver_id = (naver_id_in or "").strip() or NAVER_API_KEY_ID
    eff_naver_key = (naver_key_in or "").strip() or NAVER_API_KEY
    eff_gemini = (gemini_in or "").strip() or GEMINI_API_KEY

    st.write("🟢 네이버 API" if (eff_naver_id and eff_naver_key) else "🔴 네이버 API (키 필요)")
    st.write("🟢 Gemini AI" if eff_gemini else "🔴 Gemini AI (키 필요)")

    st.divider()
    st.subheader("🛒 토스쇼핑 쉐어링크")
    toss_enabled = st.checkbox(
        "블로그 하단에 토스 베스트상품 박스 넣기",
        value=TOSS_ENABLED,
        help="베스트 상품 중 글 문맥에 맞는 상품을 골라 추적 링크(shortUrl)로 자동 삽입합니다.",
    )
    toss_ak = st.text_input("TOSS_ACCESS_KEY", value=TOSS_ACCESS_KEY or "", type="password")
    toss_sk = st.text_input("TOSS_SECRET_KEY", value=TOSS_SECRET_KEY or "", type="password")
    toss_pub = st.text_input("TOSS_PUBLISHER_ID (UUID)", value=TOSS_PUBLISHER_ID or "")
    toss_cnt = st.number_input("삽입 상품 개수", min_value=1, max_value=5, value=TOSS_PRODUCT_COUNT or 3, step=1)

    eff_toss_ak = (toss_ak or "").strip() or TOSS_ACCESS_KEY
    eff_toss_sk = (toss_sk or "").strip() or TOSS_SECRET_KEY
    eff_toss_pub = (toss_pub or "").strip() or TOSS_PUBLISHER_ID

    if toss_enabled and not (eff_toss_ak and eff_toss_sk and eff_toss_pub):
        st.warning("⚠️ 토스 키 3개(Access/Secret/Publisher)를 모두 입력해야 상품 박스가 들어갑니다. 없으면 글만 생성됩니다.")
    elif toss_enabled:
        st.caption("✅ 키가 있으면 글 문맥에 맞는 베스트상품 + shortUrl이 하단에 자동 삽입됩니다.")

    if st.button("🧪 토스 연결 테스트", use_container_width=True):
        if not (eff_toss_ak and eff_toss_sk):
            st.error("Access/Secret 키를 먼저 입력하세요.")
        else:
            try:
                with st.spinner("토스 API 연결 중..."):
                    items = fetch_best_selling(eff_toss_ak, eff_toss_sk, size=1)
                if items:
                    st.success(f"연결 성공! 베스트 1위: {items[0].get('displayName','')[:40]}")
                else:
                    st.warning("연결은 됐지만 상품이 0건입니다.")
            except Exception as e:
                st.error(f"연결 실패: {e}")

    with st.expander("☁️ Streamlit Cloud에 영구 저장하기"):
        st.markdown(
            "배포 앱(`...streamlit.app`)에서 새로고침해도 유지하려면 "
            "**Manage app → Settings → Secrets**에 아래를 붙여넣으세요:"
        )
        st.code(
            'NAVER_API_KEY_ID = "xxx"\n'
            'NAVER_API_KEY = "xxx"\n'
            'GEMINI_API_KEY = "xxx"\n'
            'TOSS_ACCESS_KEY = "xxx"\n'
            'TOSS_SECRET_KEY = "xxx"\n'
            'TOSS_PUBLISHER_ID = "550e8400-xxxx-xxxx-xxxx-xxxxxxxxxxxx"',
            language="toml",
        )
        st.caption("저장 후 앱을 Reboot하면 사이드바에 🟢로 표시됩니다. 사이드바 입력은 Secrets보다 우선 적용됩니다.")

    st.divider()
    st.info("💡 팁: 일괄 생성된 글(보관함)은 웹 브라우저를 '새로고침' 하거나 끄면 초기화됩니다. 생성된 글은 꼭 네이버 블로그에 복사해두세요!")


def _attach_toss_footer(blog_content, keyword):
    """토스 설정이 켜져 있으면 베스트상품 박스를 하단에 삽입. 실패해도 원본 반환."""
    if not blog_content or not toss_enabled:
        return blog_content
    if not (eff_toss_ak and eff_toss_sk and eff_toss_pub):
        return blog_content
    try:
        with st.spinner("🛒 글 문맥에 맞는 토스쇼핑 베스트상품 찾는 중..."):
            return append_toss_footer(
                blog_content,
                keyword=keyword,
                access_key=eff_toss_ak,
                secret_key=eff_toss_sk,
                publisher_id=eff_toss_pub,
                gemini_api_key=eff_gemini,
                count=int(toss_cnt),
            )
    except Exception as e:
        st.warning(f"토스 상품 삽입 실패 (글은 정상 생성됨): {e}")
        return blog_content

st.title("📝 AutoBlog 자동 포스팅 시스템")
st.markdown("네이버 뉴스 검색과 Gemini AI를 활용하여 팩트 기반의 블로그 글을 자동으로 생성합니다.")
st.divider()

# 화면을 좌우 2분할 (왼쪽: 제어부, 오른쪽: 보관함)
col_left, col_right = st.columns([1, 1], gap="large")

TOPICS = [
    ("🏠 부동산", "부동산 핫이슈"),
    ("📈 경제/증권", "경제 증권 핫이슈"),
    ("⚖️ 정치", "정치 핫이슈"),
    ("👥 사회", "사회 핫이슈"),
    ("🧬 과학/IT", "과학 IT 핫이슈"),
    ("🌍 세계/국제", "국제 핫이슈"),
    ("🎤 연예", "연예계 핫이슈"),
    ("⚽ 스포츠", "스포츠 핫이슈")
]

with col_left:
    st.subheader("🚀 블로그 글 생성기")
    
    # --- 1. 일괄 생성 버튼 ---
    st.markdown("### ⚡ 8개 카테고리 자동 일괄 생성")
    st.write("버튼 한 번으로 8개 주제의 최신 뉴스를 모두 긁어와서 글 8개를 연속으로 완성합니다. (약 2~3분 소요)")
    if st.button("🚀 8개 전체 일괄 생성 시작 (커피 한 잔 마시고 오세요!)", type="primary", use_container_width=True):
        if not eff_naver_id or not eff_naver_key or not eff_gemini:
            st.error("API 키가 설정되지 않았습니다. 사이드바 설정을 확인해주세요!")
        else:
            with st.status("로봇이 8개의 글을 순차적으로 작성하고 있습니다...", expanded=True) as status:
                for icon, topic in TOPICS:
                    st.write(f"🔄 '{icon} {topic}' 작업 중...")
                    
                    news_items = fetch_latest_news(topic, display=5, api_key_id=eff_naver_id, api_key=eff_naver_key)
                    if not news_items: 
                        st.write(f"⚠️ '{topic}' 뉴스 검색 실패. 건너뜁니다.")
                        continue
                        
                    news_items_with_content = extract_contents_from_news_items(news_items)
                    if not news_items_with_content: 
                        continue
                        
                    blog_post_content = synthesize_blog_post(news_items_with_content, topic, api_key=eff_gemini)
                    
                    if blog_post_content:
                        blog_post_content = _attach_toss_footer(blog_post_content, topic)
                        now = datetime.datetime.now()
                        ampm = "오전" if now.hour < 12 else "오후"
                        time_str = now.strftime(f"%Y-%m-%d {ampm} %I:%M")
                        
                        # 히스토리 리스트 맨 앞에 추가 (최신글이 위로 오게)
                        st.session_state.history.insert(0, {
                            "time": time_str,
                            "topic": topic,
                            "content": blog_post_content
                        })
                        st.write(f"✅ '{topic}' 완료!")
                        
                status.update(label="🎉 8개 카테고리 일괄 생성 완료!", state="complete", expanded=False)
            st.success("작업 완료! 우측 [보관함]을 확인해주세요!")

    st.divider()
    
    # --- 2. 개별 생성 영역 ---
    st.markdown("### 🔍 개별 생성 (원하는 주제만)")
    keyword_input = st.text_input("키워드 입력 (예: 삼성전자 애플)", value=SEARCH_KEYWORD)
    
    # 버튼들
    cols1 = st.columns(4)
    cols2 = st.columns(4)
    selected_topic_for_single = None
    
    for i, (icon, topic) in enumerate(TOPICS):
        target_col = cols1[i] if i < 4 else cols2[i-4]
        if target_col.button(icon, use_container_width=True):
            selected_topic_for_single = topic
            
    target_keyword = selected_topic_for_single if selected_topic_for_single else keyword_input
    
    if st.button(f"▶️ '{target_keyword}'(으)로 개별 생성", use_container_width=True):
        if not eff_naver_id or not eff_naver_key or not eff_gemini:
            st.error("API 키가 설정되지 않았습니다.")
        else:
            with st.status(f"'{target_keyword}' 작성 중...", expanded=True) as status:
                news_items = fetch_latest_news(target_keyword, display=5, api_key_id=eff_naver_id, api_key=eff_naver_key)
                news_items_with_content = extract_contents_from_news_items(news_items)
                blog_post_content = synthesize_blog_post(news_items_with_content, target_keyword, api_key=eff_gemini)
                
                if blog_post_content:
                    blog_post_content = _attach_toss_footer(blog_post_content, target_keyword)
                    now = datetime.datetime.now()
                    ampm = "오전" if now.hour < 12 else "오후"
                    time_str = now.strftime(f"%Y-%m-%d {ampm} %I:%M")
                    st.session_state.history.insert(0, {
                        "time": time_str,
                        "topic": target_keyword,
                        "content": blog_post_content
                    })
                    status.update(label="생성 완료!", state="complete", expanded=False)


# --- 우측: 보관함 영역 ---
import streamlit.components.v1 as components

with col_right:
    st.subheader("🗂️ 완성된 블로그 글 보관함")
    st.write("방금 생성된 글들이 최신순으로 여기에 쌓입니다. 원하시는 글을 펼쳐서 복사하세요!")
    
    if not st.session_state.history:
        st.info("아직 생성된 글이 없습니다. 왼쪽에서 글을 생성해보세요!")
    else:
        for idx, item in enumerate(st.session_state.history):
            # 펼침막(Expander) UI 생성
            with st.expander(f"[{item['time']}] {item['topic']} 요약", expanded=(idx==0)):
                
                # 복사 버튼 (개별 ID 부여)
                safe_text = json.dumps(item['content'])
                copy_html = f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
                </head>
                <body style="margin: 0; padding: 0;">
                    <button id="copyBtn_{idx}" style="width: 100%; padding: 10px; background-color: #ff4b4b; color: white; border: none; border-radius: 5px; cursor: pointer; font-weight: bold; font-size: 14px;">
                        📋 이 글 복사하기 (서식 포함)
                    </button>
                    
                    <script>
                        const mdText = {safe_text};
                        // 전체 글을 가운데 정렬하기 위해 div 태그로 감싸줌
                        const htmlText = "<div style='text-align: center;'>" + marked.parse(mdText) + "</div>";
                        
                        document.getElementById('copyBtn_{idx}').addEventListener('click', () => {{
                            const listener = (e) => {{
                                e.clipboardData.setData('text/html', htmlText);
                                e.clipboardData.setData('text/plain', mdText);
                                e.preventDefault();
                            }};
                            
                            document.addEventListener('copy', listener);
                            document.execCommand('copy');
                            document.removeEventListener('copy', listener);
                            
                            const btn = document.getElementById('copyBtn_{idx}');
                            btn.innerText = '✅ 복사 완료!';
                            btn.style.backgroundColor = '#28a745';
                            
                            setTimeout(() => {{
                                btn.innerText = '📋 이 글 복사하기 (서식 포함)';
                                btn.style.backgroundColor = '#ff4b4b';
                            }}, 3000);
                        }});
                    </script>
                </body>
                </html>
                """
                components.html(copy_html, height=50)
                
                # 내용 미리보기
                st.markdown(item['content'])
